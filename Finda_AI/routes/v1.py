from typing import Annotated

import sentry_sdk
from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from Finda_AI.config import config
import base64
from datetime import datetime

import requests
import boto3
import json
import random
import string
from time import sleep
import openai
from pinecone import Pinecone

import assemblyai as aai

router = APIRouter()

# --- Configuration ---
ELEVENLABS_API_KEY = config.get("ELEVENLABS_API_KEY")
S3_BUCKET_NAME = config.get("S3_BUCKET_NAME") 
AWS_ACCESS_KEY = config.get("AWS_ACCESS_KEY") 
AWS_SECRET_KEY = config.get("AWS_SECRET_KEY") 
S3_ENDPOINT = config.get("S3_ENDPOINT") 
ASSEMBLY_AI_API_KEY = config.get("ASSEMBLY_AI_API_KEY") 
PINECONE_API_KEY = config.get("PINECONE_API_KEY") 
PINECONE_ENVIRONMENT = config.get("PINECONE_ENVIRONMENT") 
OPENAI_API_KEY = config.get("OPENAI_API_KEY") 

LANGUAGE_CODE = "tr"
ELEVENLABS_MODEL_ID = "eleven_turbo_v2_5"
ELEVENLABS_TTS_URL = config.get("ELEVENLABS_TTS_URL") 

openai.api_key = OPENAI_API_KEY


FINDASO_BASE_PROMPT = """
You are Findaso's AI Advisor. Your Name is Dr. Elin. You advise customers, both users and 
providers, to find the best possible solutions.
When you feel its time,you could offer them to visit the solution links and connect with findaso. 

Note the following:
- Always try to be poilte and to the point.
- Answer in Istanbul Turkish.
- Format the response in HTML tags. like <p> merhaba! </p> .

About Findaso:
Findaso (https://www.findaso.com) operates across a wide range of industries, providing technology solutions in software, business management, retail, construction, education, robotics, AI, biotechnology, manufacturing, tourism, fintech, HR, and media.

"""

# --- Helper Functions ---
def random_string(length=8):
    """Generate a random string of fixed length."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def call_elevenlabs_tts(text):
    """Call ElevenLabs TTS API."""
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL_ID,
        "language_code": LANGUAGE_CODE,
    }
    response = requests.post(ELEVENLABS_TTS_URL, headers=headers, json=payload)
    response.raise_for_status()
    return response.content  # MP3 audio file content

def upload_to_s3(file_content, filename):
    """Upload a file to S3."""
    s3 = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY
    )
    s3.put_object(Bucket=S3_BUCKET_NAME, Key=filename, Body=file_content)
    return f"s3://{S3_BUCKET_NAME}/{filename}"


def transcribe_audio(file):

    # NOTE
    # audio_file = "./example.mp3" you could also specifiy local files
    aai.settings.api_key = "d941b6aab3c0446b996c2e355493e4cd"
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(file)
    return transcript.text


def query_knowledge_base(question, chat_history):
    """Query a knowledge base (e.g., Pinecone) and use OpenAI for Q&A."""
    # Retrieve relevant context using Pinecone
    # Initialize Pinecone

    pc = Pinecone(
        api_key=PINECONE_API_KEY
    )

    index = pc.Index("finda")
    query_vector = get_embedding(question)  # Generate embedding for the question
    results = index.query(vector=query_vector, top_k=5, include_metadata=True)
    context = [item['metadata']['text'] for item in results['matches']]

    # Generate a response using OpenAI
    messages = [
        {"role": "system", "content": FINDASO_BASE_PROMPT},
        {"role": "user", "content": question},
        {"role": "assistant", "content": "chat_history: " + json.dumps(chat_history)},
        {"role": "assistant", "content": "context: " + " ".join(context)},
    ]
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        stream=False,
        temperature=0.7
    )
    return response.choices[0].message.content


def get_embedding(text):
    """Get text embedding from OpenAI."""
    response = openai.embeddings.create(input=text, model="text-embedding-ada-002")
    return response.data[0].embedding

def upload_to_cdn(audio_content, random_filename):
    url = "https://cdn.findaso.com/cdn/custom-upload?path=ai-advisor"

    payload = {}
    files=[
    ('file',(f'{random_filename}.mp3',audio_content,'audio/mpeg'))
    ]
    headers = {}

    response = requests.request("POST", url, headers=headers, data=payload, files=files)
    response_json = response.json()
    cdn_url = f"https://cdn.findaso.com{response_json['webPath']}"
    return cdn_url



def base64_to_file(base64_string, output_file_path):
    """Decode a Base64 string and save it as a file."""
    # Decode the Base64 string
    file_data = base64.b64decode(base64_string)
    
    # Write the decoded data to a file
    with open(output_file_path, 'wb') as output_file:
        output_file.write(file_data)

    return output_file_path

@router.post("/v1/sts")
async def v1_sts(request: Request):

    start = datetime.now()
    try:
        req = await request.json()
        print(f"start Step 1: Generate random filename. - {datetime.now()}")
        random_filename = f"data_{random_string()}"

        print(f"start Step 2: Transcribe audio file. - {datetime.now()}")
        if len(req['message_audio']) > 0:
            file = base64_to_file(req['message_audio'], f'./{random_filename}.mp3')
            transcript = transcribe_audio(file)



        print(f"start Step 3: Handle Question and Answer Chain.  - {datetime.now()}")
        
        user_question = req["message"] 
        if len(req['message_audio']) > 0:
            user_question = transcript
        chat_history = [{"role": "user", "content": "Hello!"}]
        answer = query_knowledge_base(user_question, chat_history)
        answer = answer.replace('"', '\"')

        print(f"start Step 4: Call ElevenLabs TTS API.  - {datetime.now()}")
        audio_content = call_elevenlabs_tts(answer)

        print(f"start Step 5: Upload audio to Findaso CDN with filename {random_filename}.  - {datetime.now()}")
        s3_audio_url = upload_to_cdn(audio_content, random_filename)

        end = datetime.now()

        print(end - start)
        return JSONResponse({
            "text": f"{answer}",
            "result_url": "",
            "s3_audio_file_key": s3_audio_url,
            "s3_idle_anim_file_key": "Dr_Elin_Idle_animation.mp4",
            "s3_talk_anim_file_key": "Long Vid Elin_small.mp4"
            })

    except Exception as e:
        sentry_sdk.capture_exception(
            Exception("Cannot connect to a backend service during status query")
        )
