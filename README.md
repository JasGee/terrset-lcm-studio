# TerrSet LCM Studio — Metadata Validator, Spatial Aligner & .RST/.RDC Converter

**Dikembangkan oleh:** Naryama Faza Al Ghazy 
**Bidang:** Geographic Information System (GIS) & Remote Sensing — Analisis Perubahan Tutupan Lahan (LULC)

---

## Deskripsi Singkat
**TerrSet LCM Studio** adalah aplikasi GUI berbasis Python (**PyQt5 + GDAL / Rasterio**) untuk memeriksa, menyelaraskan (*spatial alignment*), dan mengonversi data raster GeoTIFF (`.tif`) menjadi pasangan file native **TerrSet / IDRISI** (**`.rst`** dan **`.rdc`**) yang 100% siap diolah pada modul **Land Change Modeler (LCM)**.

### Fitur Utama
1. **Dukungan Sampai 3 Peta LULC Sekaligus ($T_1, T_2, T_3$):**
   - $T_1$ (*Earlier Land Cover*, misal 2015)
   - $T_2$ (*Later Land Cover*, misal 2020)
   - $T_3$ (*Opsional — Actual Land Cover*, misal 2025 untuk validasi hasil prediksi)
2. **Audit Metadata Otomatis (`Tab 1`):**
   - Memeriksa kesamaan Sistem Koordinat (CRS), `ref. system` TerrSet, Tipe Data (`byte`/`integer`), Dimensi Kolom $\times$ Baris, Resolusi Spasial, Batas Koordinat (*Extent*), `NoData`, dan Kode Kelas LULC.
3. **Auto-Deteksi Zona UTM Indonesia & Sinkronisasi Legenda (`Tab 2`):**
   - Otomatis mendeteksi Zona UTM (46N–52N dan 47S–54S) dari titik tengah peta dan mengonversi resolusi derajat (`EPSG:4326`) ke satuan meter.
   - Tabel editor untuk menyamakan kode kelas (`1..N`) dan nama legenda (`code 1 : ...`) pada file `.rdc`.
4. **Penyelarasan Variabel Pendorong / *Driver Variables* (`Tab 3`):**
   - Menyelaraskan banyak peta faktor sekaligus (DEM, Kemiringan Lereng, Jarak Jalan, Jarak Sungai, Faktor Ekonomi) ke grid yang 100% identik dengan peta LULC.
   - Mendukung resampling **Bilinear / Cubic** untuk data kontinu (`real`) dan **Nearest Neighbor** untuk data kategorikal (`byte`/`integer`).
5. **Perhitungan Perubahan Luas & Export CSV (`Tab 4`):**
   - Menghitung luas setiap kelas tutupan lahan dalam **Hektar (ha)**, **$\text{km}^2$**, dan **Persentase (%)** beserta selisih perubahannya, dan dapat diekspor ke file `.csv` (Excel).

---

## Cara Menjalankan Aplikasi (Windows)

### Opsi A — Menggunakan QGIS yang Sudah Terinstal (Tanpa Install Apa Pun Lagi)
Jika di laptop Anda sudah terinstal **QGIS** (versi berapa pun):
1. Ekstrak folder ini.
2. Klik dua kali file **`Jalankan_GUI_TerrSet_LCM.bat`**.
3. Aplikasi otomatis mendeteksi Python + GDAL bawaan QGIS dan langsung membuka jendela GUI.

### Opsi B — Menggunakan Python / Anaconda Standar
Jika tidak memiliki QGIS, pastikan Python 3 sudah terinstal, lalu jalankan di terminal:
```bash
pip install -r requirements.txt
python lcm_tif_to_rst_gui.py
```
