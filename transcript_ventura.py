from pathlib import Path
import queue
import time

import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

import openai
import pydub
from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())

import os  # Importação necessária

PASTA_TEMP = Path(__file__).parent / 'temp'
PASTA_TEMP.mkdir(exist_ok=True)
ARQUIVO_AUDIO_TEMP = PASTA_TEMP / 'audio.mp3'
ARQUIVO_MIC_TEMP = PASTA_TEMP / 'mic.mp3'

def main():
    # Solicita que o usuário insira a chave API, sem exibi-la após a inserção
    if 'api_key' not in st.session_state:
        st.session_state['api_key'] = ''

    if st.session_state['api_key'] == '':
        api_key = st.text_input("Digite sua chave API OpenAI:", type='password')
        if api_key:
            st.session_state['api_key'] = api_key
            # Não usamos st.experimental_rerun()
    else:
        api_key = st.session_state['api_key']

    if st.session_state['api_key'] != '':
        client = openai.OpenAI(api_key=st.session_state['api_key'])

        if 'transcricao_mic' not in st.session_state:
            st.session_state['transcricao_mic'] = ''

        @st.cache_data
        def get_ice_servers():
            return [{'urls': ['stun:stun.l.google.com:19302']}]

        def adiciona_chunck_de_audio(frames_de_audio, chunck_audio):
            for frame in frames_de_audio:
                sound = pydub.AudioSegment(
                    data=frame.to_ndarray().tobytes(),
                    sample_width=frame.format.bytes,
                    frame_rate=frame.sample_rate,
                    channels=len(frame.layout.channels)
                )
                chunck_audio += sound
            return chunck_audio

        def transcreve_audio(caminho_audio, prompt):
            with open(caminho_audio, 'rb') as arquivo_audio:
                transcricao = client.audio.transcriptions.create(
                    model='whisper-1',
                    language='pt',
                    response_format='text',
                    file=arquivo_audio,
                    prompt=prompt,
                    stream=True  # Mantendo conforme sua versão
                )
                return transcricao

        def transcreve_tab_mic():
            prompt_mic = st.text_input('(opcional) Digite o seu prompt', key='input_mic')
            webrtx_ctx = webrtc_streamer(
                key='recebe_audio',
                mode=WebRtcMode.SENDONLY,
                audio_receiver_size=1024,
                media_stream_constraints={'video': False, 'audio': True}
            )

            if not webrtx_ctx.state.playing:
                st.write(st.session_state['transcricao_mic'])
                return

            container = st.empty()
            container.markdown('Comece a falar...')
            chunck_audio = pydub.AudioSegment.empty()
            tempo_ultima_transcricao = time.time()
            st.session_state['transcricao_mic'] = ''
            while True:
                if webrtx_ctx.audio_receiver:
                    try:
                        frames_de_audio = webrtx_ctx.audio_receiver.get_frames(timeout=1)
                    except queue.Empty:
                        time.sleep(0.1)
                        continue
                    chunck_audio = adiciona_chunck_de_audio(frames_de_audio, chunck_audio)

                    agora = time.time()
                    if len(chunck_audio) > 0 and agora - tempo_ultima_transcricao > 10:
                        tempo_ultima_transcricao = agora
                        chunck_audio.export(ARQUIVO_MIC_TEMP)
                        transcricao = transcreve_audio(ARQUIVO_MIC_TEMP, prompt_mic)
                        st.session_state['transcricao_mic'] += transcricao
                        container.write(st.session_state['transcricao_mic'])
                        chunck_audio = pydub.AudioSegment.empty()
                else:
                    break

        # TRANSCREVE AUDIO =====================================
        def transcreve_tab_audio():
            prompt_input = st.text_input('(opcional) Digite o seu prompt', key='input_audio')
            arquivo_audio = st.file_uploader('Adicione um arquivo de áudio .mp3', type=['mp3'])
            if not arquivo_audio is None:
                transcricao = client.audio.transcriptions.create(
                    model='whisper-1',
                    language='pt',
                    response_format='text',
                    file=arquivo_audio,
                    prompt=prompt_input,
                    stream=True  # Mantendo conforme sua versão
                )
                st.write(transcricao)

        # Conteúdo principal do aplicativo
        st.header('DataSage AI Transcript🎙️', divider=True)
        st.markdown('#### Transcreva áudio do microfone e de arquivos de áudio .mp3')
        tab_mic, tab_audio = st.tabs(['Microfone', 'Áudio'])
        with tab_mic:
            transcreve_tab
