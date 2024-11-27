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

# Verifica se a chave API já está armazenada na sessão
if 'api_key' not in st.session_state:
    st.session_state['api_key'] = ''

# Se a chave ainda não foi inserida, solicita ao usuário
if not st.session_state['api_key']:
    placeholder = st.empty()
    with placeholder.form(key='api_key_form'):
        api_key_input = st.text_input("Digite sua chave API OpenAI:", type='password')
        submit_button = st.form_submit_button("Confirmar")
    if submit_button and api_key_input:
        st.session_state['api_key'] = api_key_input
        placeholder.empty()  # Remove o campo de entrada após a inserção
        st.experimental_rerun()
else:
    # Define a chave da API no ambiente
    os.environ["OPENAI_API_KEY"] = st.session_state['api_key']

    client = openai.OpenAI()

    if not 'transcricao_mic' in st.session_state:
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
            )
            return transcricao

    def transcreve_tab_mic():
        prompt_mic = st.text_input('(opcional) Digite o seu prompt', key='input_mic')
        webrtx_ctx = webrtc_streamer(
            key='recebe_audio',
            mode=WebRtcMode.SENDONLY,
            audio_receiver_size=1024,
            media_stream_constraints={'video': False, 'audio':True}
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
                stream=True
            )
            st.write(transcricao)

    # MAIN =====================================
    def main():
        st.header('DataSage AI Transcript🎙️', divider=True)
        st.markdown('#### Transcreva áudio do microfone e de arquivos de áudio .mp3')
        tab_mic, tab_audio = st.tabs(['Microfone', 'Áudio'])
        with tab_mic:
            transcreve_tab_mic()
        with tab_audio:
            transcreve_tab_audio()

    if __name__ == '__main__':
        main()

