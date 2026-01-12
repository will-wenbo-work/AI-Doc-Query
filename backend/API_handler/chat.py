from flask import Blueprint, request, jsonify
from langchain_core.messages import HumanMessage, SystemMessage


def _format_context(results: list[dict]) -> str:
	segments = []
	for idx, chunk in enumerate(results, start=1):
		file_name = chunk.get('file_name') or 'unknown file'
		doc_id = chunk.get('doc_id') or 'unknown doc'
		chunk_index = chunk.get('chunk_index')
		snippet = (chunk.get('text') or '').strip()
		segments.append(
			f"Segment [{idx}] — file: {file_name}, doc_id: {doc_id}, chunk: {chunk_index}\n"
			f"Content:\n{snippet}"
		)
	return '\n\n'.join(segments) if segments else 'No supporting context available.'


def _build_messages(user_query: str, context_text: str) -> list:
	system_instruction = (
		'You are a retrieval-augmented assistant for enterprise documents. '
		'Answer questions using ONLY the supplied context segments. '
		'Cite the segment numbers in square brackets (e.g., [1]) when you reference information. '
		'If the context does not contain the answer, respond with "I do not have enough information" '
		'instead of guessing. Keep answers concise and actionable.'
	)
	user_content = (
		'User Question:\n'
		f'{user_query.strip()}\n\n'
		'Retrieved Context Segments:\n'
		f'{context_text}\n\n'
		'Instructions:\n'
		'- Use only the facts in the context.\n'
		'- Cite segment numbers like [1], [2].\n'
		'- If context is insufficient, explicitly say so.'
	)
	return [
		SystemMessage(content=system_instruction),
		HumanMessage(content=user_content),
	]


def _message_to_text(message) -> str:
	content = getattr(message, 'content', '')
	if isinstance(content, str):
		return content
	if isinstance(content, list):
		parts = []
		for item in content:
			if isinstance(item, str):
				parts.append(item)
			elif isinstance(item, dict) and 'text' in item:
				parts.append(item['text'])
		return ''.join(parts)
	return str(content)


def create_chat_blueprint(embeddings, vector_store, llm):
	if embeddings is None:
		raise ValueError('embeddings client is required for chat blueprint')
	if vector_store is None:
		raise ValueError('vector store client is required for chat blueprint')
	if llm is None:
		raise ValueError('LLM client is required for chat blueprint')

	bp = Blueprint('chat_api', __name__)

	@bp.route('/chat/search', methods=['POST'])
	def search():
		payload = request.get_json(silent=True) or {}
		query = payload.get('query') or payload.get('question') or payload.get('prompt')
		if not query or not query.strip():
			return jsonify({'error': 'missing query'}), 400

		top_k = payload.get('top_k') or payload.get('k') or 5
		try:
			top_k = int(top_k)
		except (TypeError, ValueError):
			top_k = 5
		top_k = max(1, min(top_k, 20))

		try:
			query_vector = embeddings.embed_query(query)
			retrieved = vector_store.knn_search(query_vector, top_k=top_k)
		except Exception as exc:
			return jsonify({'error': 'search_failed', 'details': str(exc)}), 500

		if not retrieved:
			return jsonify({
				'query': query,
				'top_k': top_k,
				'results': [],
				'answer': 'I do not have enough information to answer that question.',
			})

		context_text = _format_context(retrieved)
		messages = _build_messages(query, context_text)

		try:
			ai_message = llm.invoke(messages)
			answer = _message_to_text(ai_message)
		except Exception as exc:
			return jsonify({
				'error': 'generation_failed',
				'details': str(exc),
				'results': retrieved,
			}), 500

		return jsonify({
			'query': query,
			'top_k': top_k,
			'results': retrieved,
			'answer': answer.strip(),
		})

	return bp
