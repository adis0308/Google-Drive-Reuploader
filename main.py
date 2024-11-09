# Author: GDPlayer.to
# Menjalankannya pakai perintah: nohup python3 main.py > output.log 2>&1 &
# Syarat sistem: ffmpeg 5+, python 3+
# Install dahulu plugin yg diperlukan dengan cara: pip install requests patool google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

import json
import os
import requests
import shutil
import subprocess
import time
import patoolib
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

current_dir = os.getcwd()
token_url = "https://www.googleapis.com/oauth2/v4/token"
credentials_file = "credentials.json"
refresh_token_file = "refresh_token.txt"
access_token_file = "access_token.json"
upload_max_retries = 15
upload_retry_delay = 5
ffmpeg_threads = '0'
video_extensions = ('.mp4', '.mkv')  # Tambahkan ekstensi lain jika perlu
data_file = "data.txt"

# Fungsi untuk membuat akses token Google Drive
def get_access_token():
    refresh_token = None
    if os.path.exists(refresh_token_file):
        with open(refresh_token_file, "r") as file:
            refresh_token = file.read()
    
    if refresh_token and os.path.exists(credentials_file):
        current_time = time.time()
        modification_time = os.path.getmtime(credentials_file)
        time_difference = current_time - modification_time
        if not os.path.exists(access_token_file) or time_difference >= 3600:
            with open(credentials_file, "r") as json_file:
                data = json.load(json_file)
                
                # Data yang dikirim ke endpoint
                token_data = {
                    "client_id": data['web']['client_id'],
                    "client_secret": data['web']['client_secret'],
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                }
            
                # Mengirim permintaan POST untuk mendapatkan access token
                response = requests.post(token_url, data=token_data)
                
                if response.status_code == 200:
                    token_info = response.json()
                    access_token = token_info['access_token']
                    
                    # Menyimpan data JSON ke dalam file
                    with open(access_token_file, 'w') as json_file:
                        json.dump(token_info, json_file, indent=4)  # indent=4 untuk format yang lebih rapi
    
                    return access_token
                else:
                    raise Exception("Gagal membuat access token: {}".format(response.content))
        else:
            with open(access_token_file, 'r') as json_file:
                data = json.load(json_file)

            return data['access_token']
    return None

# Fungsi untuk membuat service Google API Client
def create_gdrive_service():
    access_token = get_access_token()
    creds = Credentials(token=access_token)
    return build('drive', 'v3', credentials=creds)

# Fungsi untuk mengambil file id Google Drive dari link
def get_gdrive_id(link):
    file_id = None
    if 'id=' in link:
        file_id = link.split('id=')[-1].split('&')[0]
    elif 'file/d/' in link:
        file_id = link.split('/file/d/')[-1].split('/')[0]
    return file_id

# Fungsi untuk mengambil nama file dari Google Drive menggunakan googleapiclient
def get_file_name(file_id):
    try:
        service = create_gdrive_service()
        # Mendapatkan informasi file berdasarkan ID
        file = service.files().get(fileId=file_id, fields='name').execute()
        return file.get('name')
    except Exception as e:
        print('Gagal mengambil nama file dari ID "{}": {}'.format(file_id, e))
        return 'download_file'

# Fungsi untuk mendownload file dari Google Drive menggunakan googleapiclient
def download_file_from_gdrive(link, output_folder):
    try:
        file_id = get_gdrive_id(link)
        file_name = get_file_name(file_id)
        output_path = os.path.join(output_folder, file_name)
        service = create_gdrive_service()
        request = service.files().get_media(fileId=file_id)
        with open(output_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                print("Download {}%.".format(int(status.progress() * 100)))
        return output_path
    except HttpError as e:
        # Jika error karena kuota unduhan terlampaui, kembalikan None tanpa menghentikan script
        print('Gagal mendownload file "{}": {}'.format(link, str(e)))
        return None
    except Exception as e:
        print('Gagal mendownload file "{}": {}'.format(link, e))
        return None

# Fungsi untuk mengekstrak file jika berformat ZIP/RAR
def extract_file(file_path, extract_to_folder):
    try:
        patoolib.extract_archive(file_path, outdir=extract_to_folder)
        os.remove(file_path)
        print('File ZIP/RAR berhasil diekstrak ke {}'.format(extract_to_folder))
    except Exception as e:
        print('File ZIP/RAR {} gagal diekstrak karena error: \'{}\''.format(file_path, e))

# Fungsi untuk menghapus kata yang tidak diinginkan pada nama file
def remove_words(text, words_to_remove):
    for word in words_to_remove:
        text = text.replace(word, "")
    return text.strip()

# Fungsi untuk mengecek subtitle pada video dengan FFmpeg
def has_subtitle(input_video_path):
    input_path = os.path.join(current_dir, input_video_path)
    command = ["ffprobe", "-i", input_path]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    # Mencari 'Stream #x:x' dengan 'Subtitle' di output FFmpeg
    return "Subtitle" in result.stderr

# Fungsi untuk menempelkan subtitle ke video secara permanen dengan FFmpeg
def create_hardsub_video(input_video_path, output_video_path):
    video_input_path = input_video_path.split('/')
    subtitle_path = os.path.join(current_dir, *video_input_path)
    input_path = os.path.join(current_dir, input_video_path)
    output_path = os.path.join(current_dir, output_video_path)
    command = ['ffmpeg', '-hide_banner', "-threads", ffmpeg_threads, "-i", input_path, "-threads", ffmpeg_threads, "-vf", "subtitles='{}'".format(subtitle_path), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'fast', '-c:a', 'copy', '-movflags', '+faststart', '-sn', '-map_metadata', '-1', '-map_chapters', '-1', output_path]
    subprocess.run(command)

# Fungsi untuk membuat folder pada Google Drive
def create_folder_to_gdrive(folder_name):
    try:
        folder_metadata = {
            'name': folder_name,  # Ganti dengan nama folder yang diinginkan
            'mimeType': 'application/vnd.google-apps.folder'  # Tipe mime untuk folder
        }
        service = create_gdrive_service()
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        print("Folder '{}' berhasil dibuat dengan ID: {}".format(folder_name, folder.get('id')))
        return folder.get('id')
    except Exception as e:
        print('Gagal membuat folder "{}" di Google Drive: {}'.format(folder_name, e))
        return 'root'

# Fungsi untuk mengunggah file ke Google Drive dengan chunk
def upload_file_to_gdrive(file_path, file_name, folder_id):
    if not os.path.exists(file_path):
        print("File '{}' tidak ditemukan".format(file_path))
        return None
    else:
        file_size = os.path.getsize(file_path)
        chunk_size = min(1024 * 1024 * 10, file_size)  # Maksimum 10MB per chunk

        # Metadata file untuk menentukan folder
        file_metadata = {
            "name": file_name,
            'parents': [folder_id]
        }

        # Inisialisasi media upload dengan chunking
        media = MediaFileUpload(file_path, resumable=True, chunksize=chunk_size)

        # Membuat request upload
        service = create_gdrive_service()
        request = service.files().create(body=file_metadata, media_body=media, fields='id')

        response = None
        retries = 0
        max_retries = 10

        while retries < max_retries:
            try:
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        print("Upload Progress: {}%".format(int(status.progress() * 100)))
                print("Upload completed! File ID: {}".format(response.get('id')))
                return response.get('id')  # Berhasil, kembali ID file
            except HttpError as e:
                retries += 1
                if retries < max_retries:
                    print("Upload gagal (percobaan ke {}/{}), coba lagi".format(retries, max_retries))
                    time.sleep(2)  # Menunggu 2 detik sebelum mencoba lagi
                    # Coba ulang upload lagi jika gagal
                    request = service.files().create(body=file_metadata, media_body=media, fields='id')
                else:
                    print("Upload gagal setelah {} kali percobaan. Error: {}".formt(max_retries, e))
                    return None  # Gagal setelah semua retry
            except Exception as e:
                print("Gagal mengupload file '{}': {}".formt(file_name, e))
                return None
    return None

# Fungsi untuk mengunggah folder ke Google Drive
def upload_folder_to_gdrive(folder_path):
    # Membuat folder di Google Drive
    folder_name = os.path.basename(folder_path)
    folder_id = create_folder_to_gdrive(folder_name)

    # Mengiterasi file di dalam folder
    for root, dirs, files in os.walk(folder_path):
        for file_name in files:
            # Dapatkan path lengkap file
            file_path = os.path.join(root, file_name)

            # Cek apakah file adalah video
            if file_name.lower().endswith(video_extensions):
                # Menghapus kata-kata tertentu dari nama file
                words_to_remove = ["[Kusonime]", "Kusonime -", "[Nimegami]", "[Zen-Kuso]", "[Animeichi]", "MegumiNime", "[Doronime]", "[RAZ]", "[KN-Bentoo]", "[KS]", "[AWSubs]", "Kusonime", "[RebahSubs]", "[vxsub]"]
                new_file_name = remove_words(file_name, words_to_remove)

                # Periksa apakah ada subtitle
                if has_subtitle(file_path):
                    output_video_path = os.path.join(root, "hardsubbed_{}".format(new_file_name))
                    create_hardsub_video(file_path, output_video_path)
                    video_to_upload = output_video_path

                    # Hapus file setelah dibuat hardsub
                    os.remove(file_path)
                else:
                    video_to_upload = file_path
                
                upload_file_to_gdrive(video_to_upload, new_file_name, folder_id)

# Fungsi untuk menghapus folder dan semua isinya
def remove_folder_and_contents(folder_path):
    # Cek apakah folder ada
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        # Hapus folder beserta isinya
        shutil.rmtree(folder_path)
        print("Folder '{}' beserta isinya berhasil dihapus.".format(folder_path))
    else:
        print("Folder '{}' tidak ditemukan.".format(folder_path))

# Baca dan ekstrak perbaris file data
with open(data_file) as file:
    lines = file.readlines()
    for line in lines:
        ex = line.split("|")
        output_folder = ex[0].strip()
        gdrive_link = ex[1].strip()
        
        # Buat folder jika belum ada
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        # Download file dari Google Drive
        downloaded_file = download_file_from_gdrive(gdrive_link, output_folder)
        if downloaded_file is None:
            # Hapus folder jika tidak diperlukan
            remove_folder_and_contents(output_folder)
            continue
        else:
            # Ekstrak file jika berformat ZIP/RAR
            extract_file(downloaded_file, output_folder)
        
            # Upload folder ke Google Drive
            upload_folder_to_gdrive(output_folder)
            
            # Hapus folder jika tidak diperlukan
            remove_folder_and_contents(output_folder)
