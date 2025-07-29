from flask import Blueprint, request, jsonify, Response
import logging
import json
import base64
from PIL import Image
from io import BytesIO
from auth import auth_manager, token_required
from token_tracker import token_tracker
from conversation import Conversation

# Create chat blueprint
chat_bp = Blueprint('chat', __name__, url_prefix='/api')

log = logging.getLogger("chat_routes")

# Initialize conversation for legacy endpoints
CHAT = None

def get_conversation():
    """Get or initialize conversation instance"""
    global CHAT
    if CHAT is None:
        CHAT = Conversation()
    return CHAT

def get_ai_client_and_model(model_name="gemini-1.5-flash"):
    """Get AI client and model based on model name"""
    from gemsdk import GeminiClient
    from openai_client import OpenAIClient
    
    if model_name.startswith("gpt"):
        try:
            client = OpenAIClient()
            return client, model_name
        except Exception as e:
            raise ValueError(f"Failed to initialize OpenAI client: {str(e)}")
    else:
        try:
            client = GeminiClient()
            return client, "gemini-1.5-flash"
        except Exception as e:
            raise ValueError(f"Failed to initialize Gemini client: {str(e)}")


# ────────── Legacy Chat Endpoints ───────────────────
@chat_bp.post("/send_text")
def api_send_text():
    """Legacy text sending endpoint"""
    j = request.get_json(force=True, silent=True) or {}
    text = (j.get("text") or "").strip()
    use_ai = bool(j.get("generate_ai"))

    chat = get_conversation()
    spoken = chat.reply(text, use_ai=use_ai)

    return jsonify(spoken=spoken, success=True)


@chat_bp.post("/chat")
def api_chat():
    """Analyze text and/or image and provide a short answer with conversation context (no auth)"""
    try:
        log.info("=== Chat API called ===")
        j = request.get_json(force=True, silent=True) or {}

        # Get text, image, model, and chat history from request
        user_text = j.get("text", "").strip()
        image_data = j.get("image")
        model_name = j.get("model", "gemini-1.5-flash")
        chat_history = j.get("chatHistory", [])

        if not user_text and not image_data:
            log.error("No text or image provided in request")
            return jsonify(error="No text or image provided"), 400

        log.info(f"Received chat - Text: {'Yes' if user_text else 'No'}, Image: {'Yes' if image_data else 'No'}, Model: {model_name}")

        # Get AI client
        ai_client, actual_model = get_ai_client_and_model(model_name)

        if model_name.startswith("gpt"):
            # OpenAI handling
            messages = []
            
            # Add chat history
            for msg in chat_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages.append({"role": role, "content": content})

            # Add current message
            if user_text and image_data:
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"}
                        }
                    ]
                })
            elif image_data:
                messages.append({
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": "Please analyze this image."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"}
                        }
                    ]
                })
            else:
                messages.append({"role": "user", "content": user_text})

            # Make OpenAI call
            response_obj = ai_client.client.chat.completions.create(
                model=actual_model, messages=messages, max_tokens=4000, temperature=0.7
            )

            response_text = response_obj.choices[0].message.content

            return jsonify({
                "response": response_text,
                "model_used": actual_model,
                "success": True
            })

        else:
            # Gemini handling
            if user_text and image_data:
                response_text = ai_client.analyze_image_with_text(image_data, user_text)
            elif image_data:
                response_text = ai_client.analyze_image(image_data)
            else:
                response_text = ai_client.generate_text(user_text)

            return jsonify({
                "response": response_text,
                "model_used": actual_model,
                "success": True
            })

    except Exception as e:
        log.error(f"Chat API error: {e}")
        return jsonify(error=str(e)), 500


@chat_bp.post("/screenshot")
def api_screenshot():
    """Legacy screenshot analysis endpoint (no auth)"""
    try:
        log.info("=== Screenshot API called ===")
        j = request.get_json(force=True, silent=True) or {}
        
        image_data = j.get("image")
        user_text = j.get("text", "").strip()
        
        if not image_data:
            return jsonify(error="No image data provided"), 400

        # Get AI client
        ai_client, actual_model = get_ai_client_and_model("gemini-1.5-flash")

        if user_text:
            response_text = ai_client.analyze_image_with_text(image_data, user_text)
        else:
            response_text = ai_client.analyze_image(image_data)

        return jsonify({
            "response": response_text,
            "model_used": actual_model,
            "success": True
        })

    except Exception as e:
        log.error(f"Screenshot API error: {e}")
        return jsonify(error=str(e)), 500


# ────────── Protected Chat Endpoints ───────────────────
@chat_bp.post("/chat_protected")
@token_required
def api_chat_protected(current_user):
    """Protected chat endpoint with authentication and token tracking"""
    try:
        log.info(f"=== Protected Chat API called by user {current_user['id']} ===")
        j = request.get_json(force=True, silent=True) or {}

        user_text = j.get("text", "").strip()
        image_data = j.get("image")
        model_name = j.get("model", "gemini-1.5-flash")
        chat_history = j.get("chatHistory", [])
        custom_prompt = j.get("customPrompt", "").strip()

        if not user_text and not image_data:
            return jsonify(error="No text or image provided"), 400

        log.info(f"Protected chat - User: {current_user['id']}, Model: {model_name}")

        # Get AI client
        ai_client, actual_model = get_ai_client_and_model(model_name)

        if model_name.startswith("gpt"):
            # OpenAI handling with custom prompt
            messages = []
            
            if custom_prompt:
                messages.append({"role": "system", "content": custom_prompt})

            # Add chat history
            for msg in chat_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages.append({"role": role, "content": content})

            # Add current message
            if user_text and image_data:
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"}
                        }
                    ]
                })
            elif image_data:
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Please analyze this image."},
                        {
                            "type": "image_url", 
                            "image_url": {"url": f"data:image/png;base64,{image_data}"}
                        }
                    ]
                })
            else:
                messages.append({"role": "user", "content": user_text})

            # Make OpenAI call
            response_obj = ai_client.client.chat.completions.create(
                model=actual_model, messages=messages, max_tokens=4000, temperature=0.7
            )

            response_text = response_obj.choices[0].message.content

            # Log token usage for OpenAI
            token_tracker.log_openai_usage(
                user_id=current_user["id"],
                model_name=actual_model,
                endpoint="/api/chat_protected",
                response=response_obj,
                request_type="chat"
            )

            return jsonify({
                "response": response_text,
                "model_used": actual_model,
                "success": True
            })

        else:
            # Gemini handling
            conversation_parts = []
            
            if custom_prompt:
                conversation_parts.append(f"System: {custom_prompt}")

            for msg in chat_history:
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")
                conversation_parts.append(f"{role}: {content}")

            if user_text and image_data:
                combined_prompt = f"Context: {chr(10).join(conversation_parts[-5:]) if conversation_parts else ''}{chr(10)}{user_text}"
                response_text = ai_client.analyze_image_with_text(image_data, combined_prompt)
            elif image_data:
                response_text = ai_client.analyze_image(image_data)
            else:
                if conversation_parts:
                    full_prompt = chr(10).join(conversation_parts) + f"{chr(10)}User: {user_text}"
                else:
                    full_prompt = user_text
                response_text = ai_client.generate_text(full_prompt)

            # Log token usage for Gemini (estimated)
            estimated_tokens = len(user_text.split()) * 1.3 if user_text else 0
            token_tracker.log_token_usage(
                user_id=current_user["id"],
                model_name=actual_model,
                endpoint="/api/chat_protected",
                total_tokens=int(estimated_tokens),
                request_type="chat"
            )

            return jsonify({
                "response": response_text,
                "model_used": actual_model,
                "success": True
            })

    except Exception as e:
        log.error(f"Protected chat API error: {e}")
        return jsonify(error=str(e)), 500


@chat_bp.post("/screenshot_protected")
@token_required
def api_screenshot_protected(current_user):
    """Protected screenshot analysis endpoint"""
    try:
        log.info(f"=== Protected Screenshot API called by user {current_user['id']} ===")
        j = request.get_json(force=True, silent=True) or {}
        
        image_data = j.get("image")
        user_text = j.get("text", "").strip()
        model_name = j.get("model", "gemini-1.5-flash")
        
        if not image_data:
            return jsonify(error="No image data provided"), 400

        # Get AI client
        ai_client, actual_model = get_ai_client_and_model(model_name)

        if user_text:
            response_text = ai_client.analyze_image_with_text(image_data, user_text)
        else:
            response_text = ai_client.analyze_image(image_data)

        # Log token usage (estimated)
        estimated_tokens = len(user_text.split()) * 1.3 if user_text else 100
        token_tracker.log_token_usage(
            user_id=current_user["id"],
            model_name=actual_model,
            endpoint="/api/screenshot_protected",
            total_tokens=int(estimated_tokens),
            request_type="screenshot"
        )

        return jsonify({
            "response": response_text,
            "model_used": actual_model,
            "success": True
        })

    except Exception as e:
        log.error(f"Protected screenshot API error: {e}")
        return jsonify(error=str(e)), 500


# ────────── Streaming Endpoints ───────────────────
@chat_bp.post("/chat_protected_stream")
@token_required
def api_chat_protected_stream(current_user):
    """Protected streaming chat endpoint"""
    try:
        log.info(f"=== Protected Chat Stream API called by user {current_user['id']} ===")
        j = request.get_json(force=True, silent=True) or {}

        user_text = j.get("text", "").strip()
        image_data = j.get("image")
        model_name = j.get("model", "gemini-1.5-flash")
        chat_history = j.get("chatHistory", [])
        custom_prompt = j.get("customPrompt", "").strip()

        if not user_text and not image_data:
            return jsonify(error="No text or image provided"), 400

        # Get AI client
        ai_client, actual_model = get_ai_client_and_model(model_name)

        def generate_stream():
            try:
                if model_name.startswith("gpt"):
                    # OpenAI streaming
                    messages = []
                    
                    if custom_prompt:
                        messages.append({"role": "system", "content": custom_prompt})

                    for msg in chat_history:
                        role = msg.get("role", "user")
                        content = msg.get("content", "")
                        messages.append({"role": role, "content": content})

                    if user_text and image_data:
                        messages.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_text},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{image_data}"}
                                }
                            ]
                        })
                    else:
                        messages.append({"role": "user", "content": user_text})

                    # Stream from OpenAI
                    for chunk in ai_client.chat_with_history_stream(messages, actual_model):
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"

                else:
                    # Gemini streaming
                    conversation_parts = []
                    
                    if custom_prompt:
                        conversation_parts.append(f"System: {custom_prompt}")

                    for msg in chat_history:
                        role = "User" if msg.get("role") == "user" else "Assistant"
                        content = msg.get("content", "")
                        conversation_parts.append(f"{role}: {content}")

                    if user_text and image_data:
                        combined_prompt = f"Context: {chr(10).join(conversation_parts[-5:]) if conversation_parts else ''}{chr(10)}{user_text}"
                        for chunk in ai_client.analyze_image_with_text_stream(image_data, combined_prompt):
                            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                    elif image_data:
                        for chunk in ai_client.analyze_image_stream(image_data):
                            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                    else:
                        if conversation_parts:
                            full_prompt = chr(10).join(conversation_parts) + f"{chr(10)}User: {user_text}"
                        else:
                            full_prompt = user_text
                        for chunk in ai_client.generate_text_stream(full_prompt):
                            yield f"data: {json.dumps({'chunk': chunk})}\n\n"

                # Send completion signal
                yield f"data: {json.dumps({'complete': True})}\n\n"

            except Exception as e:
                log.error(f"Streaming error: {e}")
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
        log.error(f"Protected chat stream API error: {e}")
        return jsonify(error=str(e)), 500


@chat_bp.post("/screenshot_protected_stream")
@token_required
def api_screenshot_protected_stream(current_user):
    """Protected streaming screenshot analysis endpoint"""
    try:
        log.info(f"=== Protected Screenshot Stream API called by user {current_user['id']} ===")
        j = request.get_json(force=True, silent=True) or {}
        
        image_data = j.get("image")
        user_text = j.get("text", "").strip()
        model_name = j.get("model", "gemini-1.5-flash")
        
        if not image_data:
            return jsonify(error="No image data provided"), 400

        # Get AI client
        ai_client, actual_model = get_ai_client_and_model(model_name)

        def generate_stream():
            try:
                if user_text:
                    for chunk in ai_client.analyze_image_with_text_stream(image_data, user_text):
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                else:
                    for chunk in ai_client.analyze_image_stream(image_data):
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"

                # Send completion signal
                yield f"data: {json.dumps({'complete': True})}\n\n"

            except Exception as e:
                log.error(f"Screenshot streaming error: {e}")
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
        log.error(f"Protected screenshot stream API error: {e}")
        return jsonify(error=str(e)), 500 