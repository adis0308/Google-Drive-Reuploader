# Tutorial Hardsubbed + Reupload ke Google Drive
1. Buat refresh token dan simpan ke dalam file refrest_token.txt yang berguna untuk membuat access token;
2. Masukkan nama folder tempat menyimpan file batch/video yang akan didownload dan link Google Drive sumber pada file data.txt;
3. Jalankan file python melalui terminal dengan perintah ```python main.py``` atau jika ingin menjalankannya di latar belakang bisa menggunakan perintah ```nohup main.py > output.log 2>&1 &```.

Alur kerja main.py
---
1. Membaca file data.txt dan mengekstraknya;
2. Membuat file access_token.json secara otomatis;
3. Mendownload file video/batch yang telah diatur pada file data.txt;
4. Mengekstrak file jika itu rar/zip;
5. Mengkonversi/meng-hardsubbed video jika ditemukan file soft subtitle didalamnya;
6. Mengupload video tersebut ke dalam folder di Google Drive dengan nama yang sama yang telah ditentukan pada file data.txt;
7. Selesai.
