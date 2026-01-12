from typing import List

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from requests_aws4auth import AWS4Auth


class OpenSearchVectorStore:
    def __init__(self, host: str, index_name: str, region: str, service: str = 'aoss', dimension: int = 1536):
        session = boto3.Session(region_name=region)
        credentials = session.get_credentials()
        if credentials is None:
            raise RuntimeError('unable to locate AWS credentials for OpenSearch client')
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            region,
            service,
            session_token=credentials.token,
        )
        self.index_name = index_name
        self.dimension = dimension
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )
        self.ensure_index()

    def ensure_index(self):
        if self.client.indices.exists(self.index_name):
            return
        body = {
            'settings': {
                'index': {
                    'knn': True,
                }
            },
            'mappings': {
                'properties': {
                    'doc_id': {'type': 'keyword'},
                    'file_name': {'type': 'text'},
                    's3_url': {'type': 'keyword'},
                    'chunk_index': {'type': 'integer'},
                    'uploader_id': {'type': 'keyword'},
                    'uploader_name': {'type': 'keyword'},
                    'embedding': {
                        'type': 'knn_vector',
                        'dimension': self.dimension,
                        'method': {
                            'name': 'hnsw',
                            'engine': 'faiss',
                            'space_type': 'l2',
                        },
                    },
                    'text': {'type': 'text'},
                }
            },
        }
        self.client.indices.create(self.index_name, body=body)

    def delete_chunks_for_doc(self, doc_id: str):
        self.client.delete_by_query(
            index=self.index_name,
            body={'query': {'term': {'doc_id': doc_id}}},
            conflicts='proceed',
        )

    def upsert_chunks(self, records: List[dict]):
        actions = (
            {
                '_op_type': 'index',
                '_index': self.index_name,
                '_id': record['id'],
                '_source': record,
            }
            for record in records
        )
        helpers.bulk(self.client, actions)

    def knn_search(self, query_vector: List[float], top_k: int = 5, source_fields: List[str] | None = None):
        if not isinstance(query_vector, list):
            raise ValueError('query_vector must be a list of floats')
        if self.dimension and len(query_vector) != self.dimension:
            raise ValueError(f'query_vector dimension {len(query_vector)} does not match index dimension {self.dimension}')
        top_k = max(1, min(int(top_k), 50))
        body = {
            'size': top_k,
            'query': {
                'knn': {
                    'embedding': {
                        'vector': query_vector,
                        'k': top_k,
                    }
                }
            },
        }
        if source_fields:
            body['_source'] = source_fields
        resp = self.client.search(index=self.index_name, body=body)
        hits = resp.get('hits', {}).get('hits', [])
        results = []
        for hit in hits:
            source = hit.get('_source', {})
            results.append(
                {
                    'id': hit.get('_id'),
                    'score': hit.get('_score'),
                    'doc_id': source.get('doc_id'),
                    'file_name': source.get('file_name'),
                    's3_url': source.get('s3_url'),
                    'chunk_index': source.get('chunk_index'),
                    'text': source.get('text'),
                    'uploader_id': source.get('uploader_id'),
                    'uploader_name': source.get('uploader_name'),
                }
            )
        return results
