from flask import Blueprint, request, jsonify, Response
import logging
import json
import asyncio
from auth import token_required
from meeting_assistant import meeting_assistant

# Create meeting blueprint
meeting_bp = Blueprint('meeting', __name__, url_prefix='/api/meeting-assistant')

log = logging.getLogger("meeting_routes")


@meeting_bp.post("/suggest")
@token_required
def api_meeting_assistant_suggest(current_user):
    """Generate response suggestion based on conversation history"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        conversation_history = data.get("conversation_history", "")
        model = data.get("model", "gpt-4")
        custom_prompt = data.get("custom_prompt")

        log.info(
            f"Meeting assistant request from user {current_user['id']}, model: {model}"
        )

        # Generate response suggestion
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                meeting_assistant.generate_response_suggestion(
                    conversation_history=conversation_history,
                    model=model,
                    custom_prompt=custom_prompt,
                )
            )
        finally:
            loop.close()

        return jsonify(result), 200

    except Exception as e:
        log.error(f"Meeting assistant error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@meeting_bp.post("/suggest-stream")
@token_required
def api_meeting_assistant_suggest_stream(current_user):
    """Generate response suggestion with streaming using Server-Sent Events"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        conversation_history = data.get("conversation_history", "")
        model = data.get("model", "gpt-4")
        custom_prompt = data.get("custom_prompt")

        log.info(
            f"Meeting assistant streaming request from user {current_user['id']}, model: {model}"
        )

        def generate_stream():
            try:
                # Generate streaming response
                for chunk in meeting_assistant.generate_response_suggestion_stream(
                    conversation_history=conversation_history,
                    model=model,
                    custom_prompt=custom_prompt,
                ):
                    yield f"data: {json.dumps(chunk)}\n\n"

                # Send completion signal
                yield f"data: {json.dumps({'complete': True})}\n\n"

            except Exception as e:
                log.error(f"Meeting assistant streaming error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return Response(
            generate_stream(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        )

    except Exception as e:
        log.error(f"Meeting assistant streaming API error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500 