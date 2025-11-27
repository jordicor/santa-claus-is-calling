###########
###########
# App flow: phone call enters Twilio and the first function executed is Answer, from there it sends it to the Stream function, which initializes others, including Deepgram which will listen to receive audio from Stream and transcribe it.
# Every time it transcribes something, the get_transcription_add_call_sid function is activated which receives the transcription, from there it interprets it, sends it to GPT and receives the response which is also interpreted and passed to TTS to respond by voice or executes the functions requested by GPT.
###########

# Import necessary libraries
import io
import os
import re
import re
import subprocess
import sys
import json
import time
import uuid
import wave
import pydub
import emoji
import orjson
import atexit
import base64
import openai
import random
import psutil
import string
import aiohttp
import asyncio
import audioop
import logging
import sqlite3
import aiofiles
import requests
import tempfile
import threading
import pytz, sqlite3, uuid
import numpy as np
from io import BytesIO
from queue import Queue
from asyncio import sleep
from pytz import timezone
from scipy.io import wavfile
from datetime import datetime
from deepgram import Deepgram
from dotenv import load_dotenv
from pydub import AudioSegment
from pydantic import BaseModel
from twilio.rest import Client
from aiohttp import ClientSession
from multiprocessing import Value
from urllib.parse import urlencode
from starlette.routing import Route
from queue import PriorityQueue, Queue
from starlette.responses import Response
from fastapi.staticfiles import StaticFiles
from concurrent.futures import ThreadPoolExecutor
from twilio.base.exceptions import TwilioRestException
from websockets.exceptions import ConnectionClosedError
from apscheduler.schedulers.background import BackgroundScheduler
from twilio.twiml.voice_response import Connect, VoiceResponse, Stream
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, HTMLResponse
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, HTTPException, status

from asyncio import ensure_future

app = FastAPI()

# Start scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Load environment variables from .env file
load_dotenv()

# Access the DATABASE variable
dbname = os.getenv("DATABASE")

# Get the number of physical CPUs
num_cpus = psutil.cpu_count(logical=False)

# Calculate max_pool according to the given formula
max_pool = num_cpus * 2 + 1

# Initialize credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'g_credentials.json'

llm_ai = os.getenv("LLM_AI")
if llm_ai == "Claude":
    model_ai = os.getenv("MODEL_CLAUDE")
    rol = "santa-calling_1_Claude"
else: 
    model_ai = os.getenv("MODEL_GPT")
    rol = "santa-calling_1"
    
print(f"model_ai: {model_ai}")

openai_key = os.getenv("OPENAI_KEY")
claude_key = os.getenv('ANTHROPIC_API_KEY')
account_sid = os.getenv("TWILIO_SID")
auth_token = os.getenv("TWILIO_AUTH")
elevenlabs_key = os.getenv("ELEVEN_KEY")
deepgram_key = os.getenv("DEEPGRAM_KEY")
websockets_url = os.getenv("WEBSOCKET_URL")
intro_audio_url = os.getenv("INTRO_AUDIO_URL")

openai.api_key = openai_key
twilio_client = Client(account_sid, auth_token)

# Define a Pydantic model for the cancel-call request body
class CancelCallRequest(BaseModel):
    user_id: int

accumulated_transcript = ""
last_received_time = None

# Load MP3 files into memory at application startup
intro_spanish_mp3 = None
intro_english_mp3 = None

#rol = "david"
role_file_path = f"roles/{rol}.txt"
conversations = {}
connector = {}
session = {}
TTS_Index = {}
TTS_Queue = {}
TTS_Audio = {}
connected_websockets = {}
gpt_arguments = {}
gpt_talking = {}
deepgram_live = {}
full_transcription = {}
time_transcription = {}
call_extra_info = {}


# Using the emoji code name
phone_emoji = emoji.emojize(':telephone:')

query_params = ""


async def load_mp3_files():
    global intro_spanish_mp3, intro_english_mp3
    
    async with aiofiles.open("static/audio/intro-Spanish.mp3", mode='rb') as f:
        intro_spanish_mp3 = await f.read()
    
    async with aiofiles.open("static/audio/intro-English.mp3", mode='rb') as f:
        intro_english_mp3 = await f.read()

def get_db_connection():
    conn = sqlite3.connect(dbname)
    return conn

def is_localhost(request: Request) -> bool:
    """Check if request comes from localhost (internal communication only)."""
    client_host = request.client.host if request.client else None
    return client_host in ("127.0.0.1", "::1")


async def setup_deepgram_sdk(call_sid, streamSid):
    global received_handler, gpt_talking, call_extra_info
    deepgram = Deepgram(deepgram_key)

    try:
        deepgram_live[call_sid] = await deepgram.transcription.live({'smart_format': True,'interim_results': True,'language': call_extra_info[call_sid]['lang'],'model': 'nova-2', 'encoding': 'mulaw', 'sample_rate': 8000})        
        
    except ConnectionClosedError as e:
        print(f'Connection closed with code {e.code} and reason {e.reason}.')
        return None
    except Exception as e:
        print(f'Could not open socket: {e}')
        return None

    # Add an event listener for when the streaming connection closes.
    deepgram_live[call_sid].registerHandler(deepgram_live[call_sid].event.CLOSE, handle_closing_event)
   

    async def get_transcription_add_call_sid(transcription):
        global accumulated_transcript, last_received_time, sentence_transcript, mensajes, deepgram_live, received_handler, connected_websockets, gpt_talking, full_transcription, time_transcription
        
        id_unico = random.uniform(1, 100000)
        #print(f"{call_sid} ->entra get_transcription_add_call_sid, {id_unico}")
        
        # Call the function that updates the timer. Now, 'timer' in call_extra_info[call_sid] represents the remaining time.
        update_timer(call_sid, False)

        # Safety measure to ensure it doesn't last more than 30 minutes
        time_lapsed = round(time.time() - int(call_extra_info[call_sid]['start_time']))
        if time_lapsed >= 1890:
            await hang_up_call(call_sid)

        # Further below, if there are 25 seconds left, GPT is instructed to say goodbye and hang up
        # In case it hasn't done so or the goodbye is taking too long
        # A 90-second grace period is given and if reached, the call is cut.
        if call_extra_info[call_sid]['remaining_time'] <= -90:
            print(f"{call_sid} - TIME IS UP!!")
            await hang_up_call(call_sid)

        
        mensajes = []

        if call_sid not in full_transcription:
            full_transcription[call_sid] = ""
            
        if "channel" in transcription:
            sentence_transcript = transcription["channel"]["alternatives"][0]["transcript"]
        else:
            sentence_transcript = None

        # If sentence_transcript has something (is not None), then it has transcribed text
        if (sentence_transcript):

            if transcription["is_final"]:

                # Sometimes (very rarely) it detects only a part but doesn't mark it as finalized
                # Set a timeout of maximum 5 seconds to send it.
                if call_sid in time_transcription:
                    transcription_elapsed_time = time.time() - time_transcription[call_sid] 
                    if round(transcription_elapsed_time) >= 5:
                        del time_transcription[call_sid] 
                        transcription["speech_final"] = True

                if transcription["speech_final"]:
                
                    if call_sid in time_transcription:
                        del time_transcription[call_sid]
                    
                    deepgram_live[call_sid].deregister_handler(deepgram_live[call_sid].event.TRANSCRIPT_RECEIVED, get_transcription_add_call_sid)

                    if gpt_talking[call_sid] == False:

                        # If it doesn't exist, don't add space when concatenating to avoid a space at the beginning of the text
                        if full_transcription[call_sid]:
                            full_transcription[call_sid] += " "
                        full_transcription[call_sid] += sentence_transcript

                        if call_extra_info[call_sid]['remaining_time'] <= 90: # If 90 seconds or less remain, notify so responses are shorter
                            print("90 seconds remaining!")
                            full_transcription[call_sid] += "⌛️"
                        elif call_extra_info[call_sid]['remaining_time'] <= 30: # If 30 seconds or less remain, tell GPT to start saying goodbye
                            print("TIME IS UP!")
                            full_transcription[call_sid] += "⏰️"

                        print(f"{call_sid} - FINAL TRANSCRIPTION: {full_transcription[call_sid]}")

                        # Retrieve the message history of the current call (the call_sid).
                        message_history = conversations[call_sid]

                        user_message = {"role": "user", "content": full_transcription[call_sid]}
                        
                        # Before sending to GPT-4, add to message history because it must have both what has been said now and before so GPT-4 has the complete context.
                        message_history.append(user_message)

                        # Send the message history (with the current one already added after transcription) to GPT-4 to respond to what was just said in the call.
                        full_content, message_history = await send_msg_gpt(session, call_sid, message_history, streamSid, llm_ai)
                        full_transcription[call_sid] = ""
                    else:
                        print(f"{call_sid} - user talking while Santa talks (currently does not stop even if talking): {sentence_transcript}")

                    received_handler = deepgram_live[call_sid].registerHandler(deepgram_live[call_sid].event.TRANSCRIPT_RECEIVED, get_transcription_add_call_sid)
                    #print("DeepgramLive Activado")
                else:
                    if gpt_talking[call_sid] == False:
                        # If it doesn't exist, don't add space when concatenating to avoid a space at the beginning of the text
                        if full_transcription[call_sid]:
                            full_transcription[call_sid] += " "
                        full_transcription[call_sid] += sentence_transcript
                        print(f"{call_sid} - PARTIAL TRANSCRIPTION: {sentence_transcript}")
                        print(f"{call_sid} - Accumulated transcription: {full_transcription[call_sid]}")

                        # If more than 3 seconds pass without sending, then send it
                        if call_sid not in time_transcription:
                            time_transcription[call_sid] = time.time()
                        
                    else:
                        print(f"{call_sid} - user talking while Santa is talking, detection in progress: {sentence_transcript}")
                    

        #print(f"{call_sid} ->sale get_transcription_add_call_sid, {id_unico}")

    
    # Add event listener for when audio is received and send whatever is transcribed to get_transcription_add_call_sid with the transcription as arguments.
    received_handler = deepgram_live[call_sid].registerHandler(deepgram_live[call_sid].event.TRANSCRIPT_RECEIVED, get_transcription_add_call_sid)

    return deepgram_live[call_sid]


def update_timer(call_sid, update_db):
    # Calculate elapsed time
    time_lapsed = round(time.time() - int(call_extra_info[call_sid]['start_time']))
    #print(f"{call_sid} - time_lapsed: {time_lapsed}")

    # Calculate remaining time and ensure it's not negative
    call_extra_info[call_sid]['remaining_time'] = int(call_extra_info[call_sid]['timer']) - time_lapsed

    # Calculating hours, minutes and seconds
    hours = call_extra_info[call_sid]['remaining_time'] // 3600
    minutes = (call_extra_info[call_sid]['remaining_time'] % 3600) // 60
    seconds = call_extra_info[call_sid]['remaining_time'] % 60

    # Displaying the result in hours:minutes:seconds format
    if seconds % 5 == 0:
        formatted_time = f"{hours}:{minutes:02d}:{seconds:02d}"
        print(f"{call_sid} - Remaining Time: {formatted_time}")

    if update_db:
        # Info to update in the DB
        unique_id = call_extra_info[call_sid]['id']
        remaining_time = call_extra_info[call_sid]['remaining_time']

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            # Update the timer value in the database
            cursor.execute("""
                            UPDATE calls
                            SET timer = ?
                            WHERE user_id = ?
                           """, (remaining_time, unique_id))

            conn.commit()
            print(f"Timer updated correctly for ID {unique_id}.")
        except sqlite3.Error as error:
            print(f"Error updating timer in database: {error}")
        finally:
            if conn:
                conn.close()
    

# Function that manages when the connection with Deepgram closes to know if there was any error.    
async def handle_closing_event(ecode):
    if (ecode != 1000):
        print(f'Connection closed with code {ecode}.')

async def send_msg_gpt(session, call_sid, message_history, streamSid, llm_ai):
    global connected_websockets, call_extra_info

    ws = connected_websockets[call_sid]

    gpt_function_arguments = ""
    function_name = ""
    finish_reason = ""
    content = ""
    full_content = ""
    previous_tts = ""  # Track previous TTS chunk for context

    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    
    id_unico = random.uniform(1, 100000)
    #print(f"{call_sid} -->entra send_msg_gpt, {id_unico}")

    gpt_talking[call_sid] = True
    async for line in generate_chat_completion(session, call_sid, message_history):
        #print(line)
        
        if llm_ai == "GPT":
            if not line.startswith("data:"):
                continue
            else:
                # The json starts from character 5 (skipping the word "data:")
                part_data = line[6:]  # Remove "data: "

                json_data = orjson.loads(part_data)
                
                if json_data['usage'] is None:
                
                    finish_reason = json_data["choices"][0].get("finish_reason")
                    
                    if finish_reason == "stop":
                        continue
                    
                    gpt_stream = json_data["choices"][0]["delta"]
                    new_content = gpt_stream.get("content")
                    
                    full_content += new_content
                    content += filter_text(new_content)

                    # Call function that splits the text into smaller chunks so it can be sent to TTS more frequently and make it more fluid.
                    # Returns (modified_text, tts_content, remaining) or (text, None, None) if no break
                    content, tts_content, remaining = await insert_tts_break(content)

                    # If there's a chunk ready to be sent to TTS
                    if tts_content:
                        content = remaining
                        #print(f"tts_content: {tts_content}")

                        # Call to the function that converts text to speech with context
                        await tts11AI_stream(session, elevenlabs_key, tts_content, call_sid, streamSid, previous_text=previous_tts, next_text=remaining)
                        previous_tts = tts_content  # Update previous context for next chunk
                else:
                    input_tokens = json_data['usage'].get('prompt_tokens')
                    output_tokens = json_data['usage'].get('completion_tokens')
                    total_tokens = json_data['usage'].get('total_tokens')
                    break
        elif llm_ai == "Claude":
            if line.startswith("data:"):
                # The json starts from character 5 (skipping the word "data:")
                part_data = line[6:]  # Remove "data: "
                json_data = orjson.loads(part_data)
                event_type = json_data["type"]
                
                if event_type == "message_start":
                    input_tokens = json_data["message"]["usage"]["input_tokens"]
                elif event_type == "content_block_delta":
                    new_content = json_data["delta"]["text"]
                    #print(f"content: {content}")
                    
                    full_content += new_content
                    content += filter_text(new_content)

                    # Call function that splits the text into smaller chunks so it can be sent to TTS more frequently and make it more fluid.
                    # Returns (modified_text, tts_content, remaining) or (text, None, None) if no break
                    content, tts_content, remaining = await insert_tts_break(content)

                    # If there's a chunk ready to be sent to TTS
                    if tts_content:
                        content = remaining
                        #print(f"tts_content: {tts_content}")

                        # Call to the function that converts text to speech with context
                        await tts11AI_stream(session, elevenlabs_key, tts_content, call_sid, streamSid, previous_text=previous_tts, next_text=remaining)
                        previous_tts = tts_content  # Update previous context for next chunk

                elif event_type == "message_stop":
                    break
                elif event_type == "message_delta":
                    output_tokens = json_data["usage"]["output_tokens"]

            #print("entra en send_msg_gpt -> Claude")

    if (content): # In case there is any text less than 30 characters that has not been played
        await tts11AI_stream(session, elevenlabs_key, content, call_sid, streamSid, previous_text=previous_tts)    

    total_tokens = input_tokens + output_tokens
    print(f"Tokens used {llm_ai}:\ninput_tokens: {input_tokens}\noutput_tokens: {output_tokens}\ntotal_tokens: {total_tokens}")    

    # After finishing the GPT response loop, we have the complete content of what it responded
    # Create the line of what GPT responded (assistant)
    gpt_message = {"role": "assistant", "content": full_content}

    # And add it to the message history that has been sent, so that GPT knows the entire conversation
    # both the messages the user sends and the responses GPT has been giving to the user.
    message_history.append(gpt_message)

    #logger.info(f'Message history for call_sid {call_sid}: {message_history}')

    # Reviewing the full text variable
    print(f"{call_sid} - {llm_ai}: {full_content}")

    if phone_emoji in full_content:
        await send_mark_to_twilio(ws, streamSid, "hang_up")
    else:
        await send_mark_to_twilio(ws, streamSid)

    #print(f"{call_sid} -->sale send_msg_gpt, {id_unico}")

    return full_content, message_history


async def insert_tts_break(text):
    """Split text adding [T_B] marker when text exceeds 30 chars.
    Finds break point after punctuation+space or falls back to any space.
    Returns: (modified_text_with_marker, tts_content, remaining_content)
             or (original_text, None, None) if no break needed."""
    if len(text) <= 30:
        return (text, None, None)

    # Find first punctuation + space after 30 chars (excluding [T_B] marker)
    match = re.search(r"[,;!?.)\]]\s(?!\[)", text[30:])
    if match:
        punct_pos = match.start() + 30
        tts_content = text[:punct_pos+2].rstrip()
        remaining = text[punct_pos+2:].lstrip()
        return (tts_content + '[T_B]' + remaining, tts_content, remaining)

    # Fallback: find any space after 30 chars
    match = re.search(r"\s+", text[30:])
    if match:
        space_pos = match.start() + 30
        tts_content = text[:space_pos].rstrip()
        remaining = text[space_pos:].lstrip()
        return (tts_content + '[T_B]' + remaining, tts_content, remaining)

    return (text, None, None)

            
async def send_mp3_to_twilio(mp3_data: bytes, call_sid: str, stream_sid: str):
    global connected_websockets

    ws = connected_websockets[call_sid]

    # Load MP3 file from in-memory data with pydub
    audio = AudioSegment.from_file(io.BytesIO(mp3_data), format="mp3")

    # Convert audio to WAV format
    audio_wav = io.BytesIO()
    audio.export(audio_wav, format="wav")
    audio_wav.seek(0)

    # Use pydub to convert audio from WAV format to Mulaw (u-law) format with a sample rate of 8000Hz
    audio = AudioSegment.from_wav(audio_wav)
    audio = audio.set_frame_rate(8000).set_sample_width(2).set_channels(1)

    # Convert audio to Mulaw using audioop.lin2ulaw
    audio_data = audio.raw_data
    audio_data_mulaw = audioop.lin2ulaw(audio_data, audio.sample_width)

    # Stream audio to Twilio
    CHUNK_SIZE = 512
    for i in range(0, len(audio_data_mulaw), CHUNK_SIZE):
        chunk = audio_data_mulaw[i:i+CHUNK_SIZE]
        await send_audio_to_twilio(ws, chunk, stream_sid)


def read_role_prompt(file_path, call_sid):
    global call_extra_info

    # Get secret words from environment variables
    secret_instruction_word = os.getenv("SECRET_INSTRUCTION_WORD", "DefaultSecretWord1")
    secret_exit_word = os.getenv("SECRET_EXIT_WORD", "DefaultSecretWord2")

    with open(file_path, "r", encoding='utf-8') as file:
        content = file.read().strip()

        # Perform substitutions in the content
        return content.format(
            call_sid=call_sid,
            current_datetime=call_extra_info[call_sid]['current_datetime'],
            child_name=call_extra_info[call_sid]['child_name'],
            father_name=call_extra_info[call_sid]['father_name'],
            mother_name=call_extra_info[call_sid]['mother_name'],
            regalos=call_extra_info[call_sid]['gifts'],
            contexto=call_extra_info[call_sid]['context'],
            num_language=call_extra_info[call_sid]['lang'],
            secret_instruction_word=secret_instruction_word,
            secret_exit_word=secret_exit_word
        )


# Function to initialize the role message that GPT-4 will perform
def initialize_role_message(call_sid):
    global conversations, from_call_sid, query_params

    if call_sid not in conversations:
        role_prompt = read_role_prompt(role_file_path, call_sid)
        
        # Some initial "fake" phrases are added so that
        # the AI knows to continue the call from there (the
        # next thing that arrives will be the user's response),
        # which will be added to this sequence and then it responds.
        conversations[call_sid] = [
            #{"role": "user", "content": "Yes? Tell me (this line and the next one are for you to have context of the conversation, but from the next user response onwards you will have to determine if it is an answering machine or a person and then speak to them."},
            {"role": "user", "content": "Hello?"},
            {"role": "assistant", "content": "Ho, Ho, Ho! I'm Santa Claus, who do I have the pleasure of speaking with?"}
        ]

        # GPT requires that the prompt go in the first line along with the message history
        if llm_ai == "GPT":
            conversations[call_sid].insert(0, {"role": "system", "content": role_prompt})
        # Claude requires that the prompt go separately
        elif llm_ai == "Claude":
            call_extra_info[call_sid]["prompt"] = role_prompt

        #print(f"role_prompt: {role_prompt}")
        


async def generate_chat_completion(session, call_sid, message_history, model=model_ai, temperature=0.5, max_tokens=1024, streaming=True):
    if llm_ai == "GPT":

        url = f"https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}",
        }
        data = {
            "model": model,
            "messages": message_history,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True}
            
        }
                
    elif llm_ai == "Claude":
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": claude_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "messages-2023-12-15"
        }
        data = {
            "model": model,
            "system":call_extra_info[call_sid]["prompt"],
            "max_tokens": max_tokens,
            "messages": message_history,
            "temperature": temperature,
            "stream": True
        }
        
    async with session[call_sid].post(url, ssl=False, headers=headers, data=orjson.dumps(data)) as response:
        async for chunk in response.content:
            yield chunk.decode("utf-8")

    

async def send_audio_to_twilio(ws: WebSocket, chunk: bytes, streamSid: str):
    media_data = {
        "event": "media",
        "streamSid": streamSid,
        "media": {
            "payload": base64.b64encode(chunk).decode("utf-8")
        }
    }
    await ws.send_json(media_data)
    
async def send_mark_to_twilio(ws: WebSocket, streamSid: str, name = "TTS_Finished"):
    media_data = {
        "event": "mark",
        "streamSid": streamSid,
        "mark": {
            "name": name
        }
    }
    await ws.send_json(media_data)


# In case we need to transcribe text to speech that doesn't allow weird symbols or emojis.
# To prevent it from saying strange things and also to prevent code injection attempts.
def filter_text(text):
    allowed_characters = string.ascii_letters + string.digits + string.whitespace + string.punctuation + "áéíóúÁÉÍÓÚüÜñÑ"
    pattern = f"[^{re.escape(allowed_characters)}]"
    filtered_text = re.sub(pattern, "", text)
    return filtered_text

async def tts11AI_stream(session, key: str, text: str, call_sid, streamSid, voice_id: str = None, stability: float = 0.59, similarity_boost: float = 0.99, previous_text: str = "", next_text: str = ""):
    global connected_websockets, call_extra_info

    id_unico = random.uniform(1, 100000)
    #print(f"{call_sid} ** entra tts11AI_stream, {id_unico}")

    # Get voice ID from environment if not provided
    if voice_id is None:
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "Gqe8GJJLg3haJkTwYj2L")

    # Verification of active sockets
    ws = connected_websockets.get(call_sid)
    if ws is None:
        return

    if streamSid is None:
        return

    # Modified URL to request Mu-law format
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream?optimize_streaming_latency=3&output_format=ulaw_8000"

    # Modified headers for Mu-law format
    headers = {
        "Accept": "audio/basic",
        "Content-Type": "application/json",
        "xi-api-key": key
    }

    #if call_extra_info[call_sid]['lang'] == "en":
    #    model_id = "eleven_turbo_v2"
    #else:
    #    model_id = "eleven_multilingual_v2"
    
    model_id = "eleven_turbo_v2_5"

    # Data sent to the API with context for better prosody
    data = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost
        }
    }

    # Add context if provided (improves prosody and natural flow)
    if previous_text:
        data["previous_text"] = previous_text
    if next_text:
        data["next_text"] = next_text

    CHUNK_SIZE = 1024

    # Make request and handle response in Mu-law format
    async with session[call_sid].post(url, ssl=False, data=orjson.dumps(data), headers=headers) as response:
        async for chunk in response.content.iter_chunked(CHUNK_SIZE):
            if chunk:
                await send_audio_to_twilio(ws, chunk, streamSid)

    #print(f"{call_sid} ** sale tts11AI_stream, {id_unico}")


# Function to hang up the call using the call_sid provided. Uses the twilio client by updating the call with the specified call_sid
# and introduces twiml code which is Twilio's own code for managing calls.
async def hang_up_call(call_sid):
    print(f"Hanging up call")
    try:
        call = twilio_client.calls(call_sid).update(twiml=f'<Response><Hangup/></Response>')
            
    except TwilioRestException as e:
        pass


@app.websocket("/stream/{call_sid}")
async def stream(websocket: WebSocket, call_sid: str):
    global deepgram_live
    global connected_websockets, conversations, call_extra_info, connector, session

    local_websockets = websocket

    # Receives the websocket and runs an infinite loop to continuously receive data.
    await websocket.accept()

    gpt_talking[call_sid] = False
    continue_loop = True

    try:
        while continue_loop:  # while to keep the connection open

            while True: # while for conversation loop
                message = await websocket.receive_text()
                
                # If something is received in the socket but it's not text, ignore it and move to the next loop iteration.
                if message is None:
                    continue

                # Capture data messages in json format.
                data = json.loads(message)

                if data['event'] == "start":

                    print(f"Connected START received, call_sid: {call_sid}")
                   
                    parameters = data['start']
                    custom_parameters = data['start'].get('customParameters')
                    
                    if custom_parameters:

                        num_from = custom_parameters.get("num_from")
                        print(f"num_from: {num_from}")
                        
                        num_to = custom_parameters.get("num_to")
                        print(f"num_to: {num_to}")

                    call_extra_info[call_sid].update({"start_time": time.time()})                    

                    connected_websockets[call_sid] = websocket
                    
                    stream_sid = data['start']['streamSid']

                    deepgram_live[call_sid] = await setup_deepgram_sdk(call_sid, stream_sid)
                    
                    if deepgram_live[call_sid]:
                        continue_loop = True
                    else:
                        continue_loop = False
                        print("Error: Could not start deepgram_live")
                        await hang_up_call(call_sid)
                        break
                    
                    if call_sid not in conversations:
                    
                        initialize_role_message(call_sid)
                        message_history = conversations[call_sid]

                        gpt_talking[call_sid] = True
                        if call_extra_info[call_sid]['lang'] == "es":
                            await send_mp3_to_twilio(intro_spanish_mp3, call_sid, stream_sid)
                        else:
                            await send_mp3_to_twilio(intro_english_mp3, call_sid, stream_sid)
                            
                        await send_mark_to_twilio(websocket, stream_sid)

                        # Create connection pool for API requests
                        connector[call_sid], session[call_sid] = await create_pool()

                if data['event'] == "media":
                    audio = base64.b64decode(data['media']['payload'])
                    if data['media']['track'] == 'inbound':
                        if deepgram_live[call_sid]:
                            deepgram_live[call_sid].send(audio)

                if data['event'] == "stop":
                    break
                if data['event'] == "mark":
                    #print('Mark event')

                    if data['mark']['name'] == "hang_up":
                        await hang_up_call(call_sid)
                        continue
                    elif data['mark']['name'] == "TTS_Finished":
                        gpt_talking[call_sid] = False
                        continue

                # End of conversation loop

    # Display in console if the socket disconnects
    except WebSocketDisconnect:
        pass

    # Display in console if there is any unexpected exception
    except Exception as e:
        print(f"error: {str(e)}")

    # Display in console when the function finishes, close deepgram and delete the socket variable with the call_sid
    finally:
        print("Exiting")
        if continue_loop: # Don't deduct time if it exits the loop due to an error
            update_timer(call_sid, True) # Update remaining time after hanging up
            
        if deepgram_live[call_sid]:
            await deepgram_live[call_sid].finish()

        if connected_websockets.get(call_sid):
            if call_sid in full_transcription:
                del full_transcription[call_sid]
    
            if call_sid in call_extra_info:
                del call_extra_info[call_sid]
                
            if call_sid in connected_websockets:
                del connected_websockets[call_sid]

        # Close session and connector
        if call_sid in session:
            await session[call_sid].close()
            del session[call_sid]

        if call_sid in connector:
            await connector[call_sid].close()
            del connector[call_sid]

# Function that responds when a call is received to the twilio number
@app.post('/answer')
async def handle_incoming_call(request: Request):

    response = VoiceResponse()
    response.play(intro_audio_url)

    return Response(content=str(response), media_type='text/xml')


# Function that responds when a call is made to the twilio number from caller.py
@app.post('/answer2/{user_json}')
async def answer2(request: Request, user_json: str):
    global from_call_sid, query_params, call_extra_info, websockets_url

    # Data that Twilio sent when answering the call.
    form_data = await request.form()

    # Data that was sent as additional custom parameters to the call.
    query_params = request.query_params

    # Print the URL parameters (a bit of debug to verify everything is correct)
    for param in query_params.keys():
        print(f'URL Param - {param}: {query_params[param]}')

    # Assign the call_sid of the current call that twilio sends the first time when answering the call.
    call_sid = form_data["CallSid"]

    # Read and load the contents of the JSON file
    with open(f"users/{user_json}", 'r') as json_file:
        user_data = json.load(json_file)
    
    # Insert user data under the call sid in call_extra_info
    call_extra_info[call_sid] = user_data
    
    # Add the user's json filename in case it's needed for something
    call_extra_info[call_sid].update({"user_json": user_json})

    num_from = form_data["From"]
    num_to = form_data["To"]

    response = VoiceResponse()

    connect = Connect()

    stream = Stream(url=f'wss://{websockets_url}/stream/{call_sid}')

    stream.parameter(name='num_from', value=f'{num_from}')
    stream.parameter(name='num_to', value=f'{num_to}')

    connect.append(stream)
    response.append(connect)

    return Response(content=str(response), media_type='text/xml')
    
    
    
@app.post('/answer/{user_id}/{call_job_id}')
async def answer(request: Request, user_id: str, call_job_id: str):
    global call_extra_info, websockets_url

    # Retrieve form data sent by Twilio
    form_data = await request.form()
    call_sid = form_data["CallSid"]

    # Connect to SQLite database
    conn = get_db_connection()
    c = conn.cursor()

    # Verify that user_id and call_job_id match in the database
    c.execute("""
                SELECT user_details.*, calls.call_job_id, calls.timer, users.lang, calls.time_zone
                FROM users
                INNER JOIN user_details ON users.id = user_details.user_id
                INNER JOIN calls ON users.id = calls.user_id
                WHERE users.id = ? AND calls.call_job_id = ?
              """, (user_id, call_job_id))
    
    user_data = c.fetchone()

    if not user_data:
        conn.close()
        print("user or job not found")
        raise HTTPException(status_code=404, detail="User or job not found")

    # Map user data to a dictionary for easy access
    user_dict = dict(zip([column[0] for column in c.description], user_data))
    conn.close()

    # Get the user's timezone from user_dict
    user_timezone = pytz.timezone(user_dict['time_zone'])

    # Get the current date and time in the user's timezone
    current_datetime = datetime.now(user_timezone)

    # Format current_datetime as string in the desired format
    current_datetime_str = current_datetime.strftime('%Y-%m-%d')

    # Add current_datetime_str and time_zone to user_dict
    user_dict['current_datetime'] = current_datetime_str
    user_dict['time_zone'] = user_dict['time_zone']

    # Save user data for use in the call
    call_extra_info[call_sid] = user_dict
    
    num_from = form_data["From"]
    num_to = form_data["To"]

    # Create the Twilio response
    response = VoiceResponse()
    connect = Connect()
    stream = Stream(url=f'wss://{websockets_url}/stream/{call_sid}')
    
    # Additional parameters 
    stream.parameter(name='user_id', value=user_id)  
    stream.parameter(name='num_from', value=num_from)
    stream.parameter(name='num_to', value=num_to)    

    connect.append(stream)
    response.append(connect)

    return Response(content=str(response), media_type='text/xml')
    
@app.post("/schedule-call")
async def schedule_call(request: Request, user_id: str = None, call_date: str = None, call_time: str = None, time_zone: str = None, conn = None, close_conn = True):
    # Only allow internal requests from localhost
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Access denied: internal endpoint only")

    if user_id is None:
        body = await request.json() 
        user_id_from_post = body.get('user_id', None)  
        
        user_id = user_id_from_post if user_id_from_post else user_id

        if user_id is None:
            raise HTTPException(status_code=400, detail="user_id is required")

    if conn is None:
        conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT users.*, user_details.phone_number, user_details.child_name, user_details.father_name, user_details.mother_name, user_details.gifts, user_details.context, calls.call_date, calls.call_time, calls.time_zone, calls.timer
            FROM users
            JOIN user_details ON users.id = user_details.user_id
            JOIN calls ON users.id = calls.user_id
            WHERE users.id=?
        """, (user_id,))
        row = c.fetchone()
        if row:
            user_data = dict(zip([column[0] for column in c.description], row))
            call_date = user_data['call_date']
            call_time = user_data['call_time']
            time_zone = user_data['time_zone']
        else:
            print("user_id not found")
            return JSONResponse(content={'message': 'User not found'}, status_code=404)
    except sqlite3.Error as e:
        print(f"Read Database error: {e}")
        return JSONResponse(content={'message': ['error500']}, status_code=500)

    call_datetime_str = f"{call_date} {call_time}"
    call_datetime = datetime.strptime(call_datetime_str, '%Y-%m-%d %H:%M')

    user_timezone = pytz.timezone(time_zone)
    user_datetime = user_timezone.localize(call_datetime)

    converted_timezone = pytz.timezone('Europe/Madrid')
    converted_datetime = user_datetime.astimezone(converted_timezone)

    job_id = str(uuid.uuid4())
    print(f"Scheduling call for User ID: {user_id} at {converted_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')} with Job ID: {job_id}")

    job = scheduler.add_job(
        func=initiate_call,
        trigger='date',
        run_date=converted_datetime,
        args=[user_id],
        id=job_id
    )

    if conn is None:
        conn = get_db_connection()
        
    try:
        c = conn.cursor()
        c.execute("UPDATE calls SET call_job_id=? WHERE user_id=?", (job.id, user_id))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Update Database error: {e}")
        return JSONResponse(content={'message': strings_data['error500']}, status_code=500)
    finally:
        if close_conn:
            conn.close()

    return JSONResponse(content={'message': 'Call scheduled successfully', 'job_id': job_id}, status_code=200)


@app.post("/cancel-call")
async def cancel_call(request: Request, request_body: CancelCallRequest):
    # Only allow internal requests from localhost
    if not is_localhost(request):
        raise HTTPException(status_code=403, detail="Access denied: internal endpoint only")

    user_id = request_body.user_id
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        c = conn.cursor()
        c.execute("SELECT call_job_id, call_date, call_time, time_zone FROM calls WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row:
            job_id, call_date, call_time, time_zone = row

            call_datetime_str = f"{call_date} {call_time}"
            call_datetime = datetime.strptime(call_datetime_str, '%Y-%m-%d %H:%M')

            user_timezone = pytz.timezone(time_zone)
            user_datetime = user_timezone.localize(call_datetime)

            current_datetime = datetime.now(pytz.timezone(time_zone))
            if current_datetime > user_datetime:
                return JSONResponse(content={'message': 'call_already_happened'}, status_code=400)
            try:
                scheduler.remove_job(job_id)
                c.execute("UPDATE calls SET call_job_id=NULL, call_date=NULL, call_time=NULL WHERE user_id=?", (user_id,))
                conn.commit()
                return JSONResponse(content={'message': 'call_cancelled_successfully'}, status_code=200)
            except Exception as e:  # Use a more specific exception if possible
                return JSONResponse(content={'message': 'call_not_found'}, status_code=404)
        else:
            return JSONResponse(content={'message': 'user_not_found'}, status_code=404)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return JSONResponse(content={'message': 'error500'}, status_code=500)
    finally:
        conn.close()

def initiate_call(user_id):
    print(f"initiate_call with user_id: {user_id}")

    # Build a relative path from the current script location
    dir_of_current_script = os.path.dirname(__file__)
    relative_path_to_caller = os.path.join(dir_of_current_script, 'caller.py')

    # Execute the 'caller.py' script passing the user_id as an argument
    subprocess.run(["python", relative_path_to_caller, str(user_id)])       


@app.get("/schedule-pending-calls")
async def schedule_pending_calls():
    conn = get_db_connection()
    c = conn.cursor()
    c.row_factory = sqlite3.Row    
    c.execute("SELECT user_id, call_date, call_time, time_zone FROM calls")
    calls = c.fetchall()

    for call in calls:
        if call['call_date'] is None or call['call_time'] is None:
            continue
        # Regex for YYYY-MM-DD
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

        # Regex for HH:MM
        time_pattern = re.compile(r'^\d{2}:\d{2}$')

        if date_pattern.match(call['call_date']) and time_pattern.match(call['call_time']):
            user_id = call['user_id']
            tz = timezone(call['time_zone'])
            call_datetime_str = f"{call['call_date']} {call['call_time']}"
            call_datetime = datetime.strptime(call_datetime_str, '%Y-%m-%d %H:%M')
            call_datetime = tz.localize(call_datetime)

            if call_datetime > datetime.now(tz):
                await schedule_call(None, user_id, call['call_date'], call['call_time'], call['time_zone'], conn, close_conn=False)

    print("Pending calls scheduled")
    

# Async function for the pool since asyncio requires it to be inside an async function
async def create_pool():
    # Create the connector and session
    timeout = aiohttp.ClientTimeout(connect=1, sock_connect=3)
    connector = aiohttp.TCPConnector(limit=max_pool, ttl_dns_cache=300, keepalive_timeout=30)
    session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    return connector, session


async def main():
    print("------")
    print("Scheduling pending Calls..")
    await schedule_pending_calls()
    print("------")
    await load_mp3_files()


# Start the application using uvicorn for secure mode and use certificates for https
if __name__ == '__main__':
    asyncio.run(main()) # Schedule pending calls
    print("                    _...")
    print("              o_.-\"`    `\\ ")
    print("       .--.  _ `'-._.-'\"\"-;     _")
    print("     .'    `\\_\\_  {_.-a\"a-}  _ / \\ ")
    print("   _/     .-'  '. {c-._o_.){\\|`  |")
    print("  (@`-._ /       \\{    ^  } \\\\ _/")
    print("   `~\\  '-._      /'.     }  \\}  .-.")
    print("     |>:<   '-.__/   '._,} \\_/  / ())")
    print("     |     >:<   `'---. ____'-.|(`\"\"")
    print("     \\            >:<  \\\\_\\\\_\\ | ;")
    print("      \\                 \\\\-{}-\\/  \\")
    print("       \\                 '._\\\\'   /)")
    print("        '.                       /(/")
    print("          `-._ _____ _ _____ __.'\\ \\ ")
    print("            / \\     / \\     / \\   \\ \\ ")
    print("         _.'/^\\'._.'/^\\'._.'/^\\'.__) \\ ")
    print("     ,=='  `---`   '---'   '---'      )")
    print("     `\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"\"`")
    print("***********************************************")
    print("*      Santa Claus AI loaded and ready!       *")
    print("*      Use caller.py to make calls            *")
    print("***********************************************")

    # Register cleanup handlers before starting uvicorn
    atexit.register(lambda: scheduler.shutdown())

    import uvicorn

    # Function to run HTTPS server
    def run_https():
        uvicorn.run(app, host='0.0.0.0', port=7777, ssl_certfile='static/sec/cert.pem', ssl_keyfile='static/sec/privkey.pem')

    # Function to run HTTP server
    def run_http():
        uvicorn.run(app, host='0.0.0.0', port=7778)

    # Start HTTP server in a separate thread
    http_thread = threading.Thread(target=run_http, daemon=True)
    http_thread.start()
    print("HTTP server started on port 7778")

    # Run HTTPS server in main thread
    print("HTTPS server starting on port 7777")
    run_https()
