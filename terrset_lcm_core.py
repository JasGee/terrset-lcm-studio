"""
================================================================================
MODUL INTI GEOSPASIAL: TERRSET LCM VALIDATOR, ALIGNER & .RST/.RDC CONVERTER
================================================================================
Dibuat khusus untuk: Vinaryama (Mahasiswa Geografi - GIS & Remote Sensing)

Deskripsi Modul:
Modul ini menangani seluruh logika geospasial dan kartografi untuk menyiapkan:
1. Hingga 3 Peta Tutupan Lahan:
   - T1 (Earlier Land Cover, misal 2015)
   - T2 (Later Land Cover, misal 2020)
   - T3 (Opsional - Actual Land Cover untuk Validasi Prediksi, misal 2025)
2. Peta Variabel Pendorong (Driver Variables) untuk tab Transition Potentials:
   - Misalnya DEM (Elevasi), Kemiringan Lereng (Slope), Jarak dari Jalan,
     Jarak dari Sungai, Jarak dari Pusat Kota, dll.

Prinsip Metodologi Geospasial (GIS Rules):
- Pemeriksaan & Reproyeksi CRS ke sistem proyeksi metrik (UTM) dengan fitur
  Auto-Detect Zona UTM dari titik tengah (centroid) koordinat peta.
- Metode Resampling Tepat:
  * Nearest Neighbor untuk data kategorikal/tematik (LULC T1, T2, T3 & zonasi).
  * Bilinear atau Cubic untuk data kontinu (DEM, kemiringan lereng, jarak).
- Menulis langsung format native TerrSet:
  * .rst (IDRISI Raster A.1 flat binary: byte/uint8, integer/int16, real/float32)
  * .rdc (IDRISI Raster Documentation File dengan format 12-karakter key)
================================================================================
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

HAS_RASTERIO = False
HAS_GDAL = False

try:
    import rasterio
    from rasterio.crs import CRS as RioCRS
    from rasterio.transform import from_bounds as rio_from_bounds
    from rasterio.warp import Resampling as RioResampling, calculate_default_transform, reproject as rio_reproject
    HAS_RASTERIO = True
except ImportError:
    pass

try:
    from osgeo import gdal, osr
    gdal.UseExceptions()
    HAS_GDAL = True
except ImportError:
    pass


DEFAULT_CLASS_NAMES: Dict[int, str] = {
    1: "Hutan / Vegetasi Rapat",
    2: "Pertanian / Perkebunan",
    3: "Lahan Terbangun / Permukiman",
    4: "Badan Air",
    5: "Lahan Terbuka / Semak",
    6: "Kelas Tutupan Lahan 6",
    7: "Kelas Tutupan Lahan 7",
    8: "Kelas Tutupan Lahan 8",
}

# Daftar Preset Zona UTM Indonesia untuk Dropdown Pilihan Cepat di GUI
UTM_PRESETS_INDONESIA: List[Tuple[str, str, str]] = [
    ("EPSG:32747 — WGS 84 / UTM Zone 47S (Sumatera Barat/Selatan, Bengkulu, Lampung)", "EPSG:32747", "utm-47s"),
    ("EPSG:32748 — WGS 84 / UTM Zone 48S (Jawa Barat, DKI, Banten, Sumsel, Kalbar)", "EPSG:32748", "utm-48s"),
    ("EPSG:32749 — WGS 84 / UTM Zone 49S (Jawa Tengah, DIY, Jawa Timur, Kalteng, Kalsel)", "EPSG:32749", "utm-49s"),
    ("EPSG:32750 — WGS 84 / UTM Zone 50S (Bali, NTB, NTT Barat, Kaltim, Sulsel, Sulbar)", "EPSG:32750", "utm-50s"),
    ("EPSG:32751 — WGS 84 / UTM Zone 51S (NTT Timur, Sultra, Sulteng, Maluku Selatan)", "EPSG:32751", "utm-51s"),
    ("EPSG:32752 — WGS 84 / UTM Zone 52S (Maluku Tenggara, Papua Barat Daya/Selatan)", "EPSG:32752", "utm-52s"),
    ("EPSG:32753 — WGS 84 / UTM Zone 53S (Papua Tengah, Papua Selatan)", "EPSG:32753", "utm-53s"),
    ("EPSG:32754 — WGS 84 / UTM Zone 54S (Papua Pegunungan, Merauke/Timur)", "EPSG:32754", "utm-54s"),
    ("EPSG:32646 — WGS 84 / UTM Zone 46N (Aceh Barat, Sabang)", "EPSG:32646", "utm-46n"),
    ("EPSG:32647 — WGS 84 / UTM Zone 47N (Aceh Timur, Sumatera Utara, Riau Barat)", "EPSG:32647", "utm-47n"),
    ("EPSG:32648 — WGS 84 / UTM Zone 48N (Kep. Riau, Natuna, Kalbar Utara)", "EPSG:32648", "utm-48n"),
    ("EPSG:32649 — WGS 84 / UTM Zone 49N (Kalimantan Barat/Timur Bagian Utara)", "EPSG:32649", "utm-49n"),
    ("EPSG:32650 — WGS 84 / UTM Zone 50N (Kalimantan Utara, Kaltim Utara, Sulteng Utara)", "EPSG:32650", "utm-50n"),
    ("EPSG:32651 — WGS 84 / UTM Zone 51N (Sulawesi Utara, Gorontalo, Halmahera Barat)", "EPSG:32651", "utm-51n"),
    ("EPSG:32652 — WGS 84 / UTM Zone 52N (Maluku Utara / Halmahera Timur, Raja Ampat Utara)", "EPSG:32652", "utm-52n"),
]


# ==============================================================================
# 1. FUNGSI KONVERSI SISTEM KOORDINAT (CRS -> TERRSET REF. SYSTEM)
# ==============================================================================

def parse_crs_info(wkt_or_epsg: str) -> Tuple[Optional[int], bool, str, str, str]:
    """
    Menganalisis string CRS (misal 'EPSG:32749' atau WKT) dan mengembalikan:
    (epsg_code, is_projected, wkt_string, terrset_ref_system, terrset_ref_units)
    """
    if not wkt_or_epsg or wkt_or_epsg.strip().upper() == "TIDAK TERDEFINISI":
        return None, False, "", "plane", "m"

    text = wkt_or_epsg.strip()

    if HAS_GDAL:
        srs = osr.SpatialReference()
        if text.upper().startswith("EPSG:"):
            epsg_num = int(text.split(":")[1])
            srs.ImportFromEPSG(epsg_num)
        else:
            srs.ImportFromWkt(text)

        try:
            srs.AutoIdentifyEPSG()
        except Exception:
            pass

        auth_code = srs.GetAuthorityCode(None)
        epsg = int(auth_code) if auth_code and str(auth_code).isdigit() else None
        is_proj = bool(srs.IsProjected())
        wkt_out = srs.ExportToWkt()
    elif HAS_RASTERIO:
        crs_obj = RioCRS.from_user_input(text)
        epsg = crs_obj.to_epsg()
        is_proj = bool(crs_obj.is_projected)
        wkt_out = crs_obj.to_wkt()
    else:
        raise RuntimeError("Tidak ditemukan pustaka 'osgeo.gdal' maupun 'rasterio'.")

    ref_sys, ref_units = epsg_to_terrset_ref(epsg, is_proj)
    return epsg, is_proj, wkt_out, ref_sys, ref_units


def epsg_to_terrset_ref(epsg: Optional[int], is_projected: bool) -> Tuple[str, str]:
    """
    Mengubah kode EPSG menjadi nama 'ref. system' dan 'ref. units' pada file .rdc TerrSet.
    """
    if epsg is not None:
        if 32601 <= epsg <= 32660:
            return f"utm-{epsg - 32600}n", "m"
        if 32701 <= epsg <= 32760:
            return f"utm-{epsg - 32700}s", "m"
        if epsg == 4326:
            return "latlong", "deg"

    if is_projected:
        return "plane", "m"
    return "latlong", "deg"


def suggest_utm_from_metadata(meta: Dict) -> Tuple[str, str, str, float]:
    """
    Mendeteksi secara otomatis Zona UTM (EPSG, ref. system, ref. units) dan
    resolusi spasial dalam meter berdasarkan titik tengah (centroid) peta raster.
    """
    if meta["is_projected"] and meta["epsg"]:
        return f"EPSG:{meta['epsg']}", meta["ref_system"], meta["ref_units"], float(meta["res_x"])

    cx = (meta["min_x"] + meta["max_x"]) / 2.0
    cy = (meta["min_y"] + meta["max_y"]) / 2.0

    if -180.0 <= cx <= 180.0 and -90.0 <= cy <= 90.0:
        lon, lat = cx, cy
    elif HAS_GDAL and meta["crs_wkt"]:
        src_srs = osr.SpatialReference()
        src_srs.ImportFromWkt(meta["crs_wkt"])
        src_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        geo_srs = osr.SpatialReference()
        geo_srs.ImportFromEPSG(4326)
        geo_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        ct = osr.CoordinateTransformation(src_srs, geo_srs)
        lon, lat, _ = ct.TransformPoint(cx, cy)
    else:
        lon, lat = 110.0, -7.0

    zone = int((lon + 180.0) // 6.0) + 1
    zone = max(1, min(60, zone))

    if lat >= 0:
        epsg_code = 32600 + zone
        ref_sys = f"utm-{zone}n"
    else:
        epsg_code = 32700 + zone
        ref_sys = f"utm-{zone}s"

    raw_res = float(meta["res_x"])
    if not meta["is_projected"] or raw_res < 0.1:
        est_res_m = raw_res * 111319.49
        common_res = [1.0, 5.0, 10.0, 12.5, 15.0, 20.0, 25.0, 30.0, 50.0, 60.0, 100.0, 250.0, 500.0, 1000.0]
        best_res = min(common_res, key=lambda r: abs(est_res_m - r))
        if abs(est_res_m - best_res) / best_res < 0.08:
            res_m = best_res
        else:
            res_m = round(est_res_m, 2)
    else:
        res_m = round(raw_res, 4)

    return f"EPSG:{epsg_code}", ref_sys, "m", res_m


# ==============================================================================
# 2. FUNGSI INSPEKSI METADATA GEOTIFF (.TIF)
# ==============================================================================

def inspect_raster_metadata(tif_path: str) -> Dict:
    """
    Membaca metadata spasial, atribut piksel, nilai NoData, dan distribusi kelas
    unik dari file GeoTIFF (.tif).
    """
    path_obj = Path(tif_path)

    if HAS_GDAL:
        ds = gdal.Open(str(path_obj), gdal.GA_ReadOnly)
        if ds is None:
            raise ValueError(f"Gagal membuka file GeoTIFF: {path_obj}")

        width = ds.RasterXSize
        height = ds.RasterYSize
        count = ds.RasterCount
        gt = ds.GetGeoTransform()
        min_x = float(gt[0])
        res_x = float(gt[1])
        max_y = float(gt[3])
        res_y = abs(float(gt[5]))
        max_x = min_x + width * res_x
        min_y = max_y - height * res_y

        proj_wkt = ds.GetProjection()
        band = ds.GetRasterBand(1)
        dtype_str = gdal.GetDataTypeName(band.DataType).lower()
        dtype_map = {
            "byte": "uint8",
            "uint8": "uint8",
            "int16": "int16",
            "uint16": "uint16",
            "int32": "int32",
            "uint32": "uint32",
            "float32": "float32",
            "float64": "float64",
        }
        dtype_str = dtype_map.get(dtype_str, dtype_str)
        nodata_val = band.GetNoDataValue()
        arr = band.ReadAsArray()
        ds = None
    elif HAS_RASTERIO:
        with rasterio.open(path_obj) as src:
            width = src.width
            height = src.height
            count = src.count
            min_x, min_y, max_x, max_y = [float(v) for v in src.bounds]
            res_x, res_y = [float(v) for v in src.res]
            proj_wkt = src.crs.to_wkt() if src.crs else ""
            dtype_str = src.dtypes[0]
            nodata_val = src.nodata
            arr = src.read(1)
    else:
        raise RuntimeError("Pustaka GDAL atau Rasterio belum tersedia.")

    epsg, is_projected, wkt_clean, ref_sys, ref_units = parse_crs_info(proj_wkt)

    if np.issubdtype(arr.dtype, np.floating):
        arr64 = arr.astype(np.float64)
        nan_mask = np.isnan(arr64)
        if nodata_val is not None and not np.isnan(nodata_val):
            nd_f = float(nodata_val)
            if abs(nd_f) > 1e30:
                # Menangani Float32 NoData ekstrem (-3.4028235e+38 / -FLT_MAX dari ArcGIS/QGIS)
                nodata_mask = nan_mask | (arr64 <= -1e30) | (arr64 >= 1e30)
            else:
                nodata_mask = nan_mask | np.isclose(arr64, nd_f, rtol=1e-5, atol=1e-7)
        else:
            nodata_mask = nan_mask | (arr64 <= -1e30) | (arr64 >= 1e30)
    else:
        if nodata_val is not None:
            nodata_mask = (arr == int(round(nodata_val)))
        else:
            nodata_mask = np.zeros(arr.shape, dtype=bool)

    valid_pixels = arr[~nodata_mask]
    nodata_count = int(np.sum(nodata_mask))

    unique_vals, counts = np.unique(valid_pixels, return_counts=True)
    is_categorical = (not np.issubdtype(arr.dtype, np.floating)) and (len(unique_vals) <= 150)
    if np.issubdtype(arr.dtype, np.floating) and len(unique_vals) <= 30:
        # Cek apakah float tersebut sebenarnya bilangan bulat (misal hasil export GEE)
        if np.all(np.isclose(unique_vals, np.round(unique_vals))):
            is_categorical = True

    class_counts: Dict[int, int] = {}
    if is_categorical:
        for val, cnt in zip(unique_vals, counts):
            key = int(round(float(val)))
            class_counts[key] = class_counts.get(key, 0) + int(cnt)

    min_val = float(np.min(valid_pixels)) if valid_pixels.size > 0 else 0.0
    max_val = float(np.max(valid_pixels)) if valid_pixels.size > 0 else 0.0

    crs_display = f"EPSG:{epsg}" if epsg else ("Terdefinisi (Custom WKT)" if wkt_clean else "TIDAK TERDEFINISI")

    return {
        "path": str(path_obj),
        "name": path_obj.name,
        "crs_wkt": wkt_clean,
        "crs_display": crs_display,
        "epsg": epsg,
        "is_projected": is_projected,
        "ref_system": ref_sys,
        "ref_units": ref_units,
        "width": width,
        "height": height,
        "count": count,
        "res_x": res_x,
        "res_y": res_y,
        "is_square_pixel": bool(np.isclose(res_x, res_y, atol=1e-5)),
        "min_x": min_x,
        "min_y": min_y,
        "max_x": max_x,
        "max_y": max_y,
        "dtype": dtype_str,
        "nodata": nodata_val,
        "nodata_count": nodata_count,
        "min_val": min_val,
        "max_val": max_val,
        "is_categorical": is_categorical,
        "class_counts": class_counts,
    }


# ==============================================================================
# 3. FUNGSI AUDIT & PERBANDINGAN METADATA UNTUK 2 ATAU 3 PETA LULC (T1, T2, T3)
# ==============================================================================

def compare_lulc_metadata_for_lcm(
    meta1: Dict, meta2: Dict, meta3: Optional[Dict] = None
) -> List[Tuple[str, str, str, str, str]]:
    """
    Membandingkan parameter metadata T1, T2, dan (opsional) T3 terhadap syarat
    wajib Land Change Modeler (LCM) di TerrSet.
    Mengembalikan list 5-tuple: (Parameter, Nilai T1, Nilai T2, Nilai T3, Diagnosis).
    """
    metas = [meta1, meta2] + ([meta3] if meta3 is not None else [])
    rows: List[Tuple[str, str, str, str, str]] = []

    def val_t3(fn) -> str:
        return fn(meta3) if meta3 is not None else "— (Tidak Diinput)"

    # 1. CRS
    all_defined = all(bool(m["crs_wkt"]) for m in metas)
    all_same_crs = len(set(m["epsg"] or m["crs_wkt"] for m in metas)) == 1
    all_proj = all(m["is_projected"] for m in metas)
    if not all_defined:
        crs_status = "PERLU PERBAIKAN: Ada CRS yang belum terdefinisi!"
    elif not all_same_crs:
        crs_status = "PERLU REPROYEKSI: Sistem koordinat antar peta belum sama!"
    elif not all_proj:
        crs_status = "PERINGATAN GEOGRAFI: Masih derajat (Geografis), otomatis disarankan ke UTM (meter)!"
    else:
        crs_status = "OK (Identik & Terproyeksi)"
    rows.append((
        "1. Sistem Koordinat (CRS)",
        meta1["crs_display"],
        meta2["crs_display"],
        val_t3(lambda m: m["crs_display"]),
        crs_status,
    ))

    # 2. TerrSet ref. system & units
    ref_ok = (len(set(m["ref_system"] for m in metas)) == 1) and all(m["ref_units"] == "m" for m in metas)
    rows.append((
        "2. TerrSet ref. system",
        f"{meta1['ref_system']} ({meta1['ref_units']})",
        f"{meta2['ref_system']} ({meta2['ref_units']})",
        val_t3(lambda m: f"{m['ref_system']} ({m['ref_units']})"),
        "OK" if ref_ok else "PERLU DISAMAKAN (Gunakan proyeksi UTM / satuan m)",
    ))

    # 3. Tipe Data
    all_byte_int = all(m["dtype"] in ("uint8", "int16") for m in metas)
    same_dt = len(set(m["dtype"] for m in metas)) == 1
    if all_byte_int and same_dt:
        dt_status = "OK (Kompatibel dengan byte/integer TerrSet)"
    else:
        dt_status = "PERLU KONVERSI ke tipe 'byte' (uint8) atau 'integer' (int16)"
    rows.append((
        "3. Tipe Data Piksel",
        meta1["dtype"],
        meta2["dtype"],
        val_t3(lambda m: m["dtype"]),
        dt_status,
    ))

    # 4. Dimensi Kolom x Baris
    dim_fn = lambda m: f"{m['width']} kol x {m['height']} bar"
    dim_ok = (len(set((m["width"], m["height"]) for m in metas)) == 1)
    rows.append((
        "4. Dimensi (Columns x Rows)",
        dim_fn(meta1),
        dim_fn(meta2),
        val_t3(dim_fn),
        "OK (Sama persis)" if dim_ok else "PERLU ALIGNMENT: Jumlah kolom/baris belum sama!",
    ))

    # 5. Resolusi Spasial
    res_fn = lambda m: f"{m['res_x']:.5g} x {m['res_y']:.5g}"
    res_same = all(
        np.isclose(m["res_x"], meta1["res_x"], atol=1e-5) and np.isclose(m["res_y"], meta1["res_y"], atol=1e-5)
        for m in metas
    )
    res_sq = all(m["is_square_pixel"] for m in metas)
    if res_same and res_sq:
        res_status = "OK (Resolusi identik & piksel bujur sangkar)"
    elif not res_sq:
        res_status = "PERLU RESAMPLING: Piksel belum bujur sangkar (res X != res Y)"
    else:
        res_status = "PERLU RESAMPLING: Resolusi antar peta berbeda!"
    rows.append((
        "5. Resolusi Spasial",
        res_fn(meta1),
        res_fn(meta2),
        val_t3(res_fn),
        res_status,
    ))

    # 6. Batas Koordinat (Extent)
    ext_fn = lambda m: f"X:[{m['min_x']:.2f}, {m['max_x']:.2f}] Y:[{m['min_y']:.2f}, {m['max_y']:.2f}]"
    ext_same = all(
        np.isclose(m["min_x"], meta1["min_x"], atol=1e-3)
        and np.isclose(m["max_x"], meta1["max_x"], atol=1e-3)
        and np.isclose(m["min_y"], meta1["min_y"], atol=1e-3)
        and np.isclose(m["max_y"], meta1["max_y"], atol=1e-3)
        for m in metas
    )
    rows.append((
        "6. Batas Koordinat (Extent)",
        ext_fn(meta1),
        ext_fn(meta2),
        val_t3(ext_fn),
        "OK (Extent identik)" if ext_same else "PERLU SNAP/ALIGNMENT: Batas koordinat belum identik!",
    ))

    # 7. Nilai NoData / Background
    nd_fn = lambda m: f"{m['nodata']} ({m['nodata_count']:,} px)"
    nd_ok = all(m["nodata"] in (0, None) for m in metas)
    rows.append((
        "7. Nilai NoData / Background",
        nd_fn(meta1),
        nd_fn(meta2),
        val_t3(nd_fn),
        "OK (Background = 0)" if nd_ok else "PERLU REMAP: NoData akan dipetakan menjadi 0 (background)",
    ))

    # 8. Daftar Kelas LULC
    cls_fn = lambda m: ", ".join(map(str, sorted([k for k in m["class_counts"].keys() if k != 0]))) or "(Hanya 0)"
    cls_sets = [sorted([k for k in m["class_counts"].keys() if k != 0]) for m in metas]
    cls_same = all(c == cls_sets[0] and len(c) > 0 for c in cls_sets)
    rows.append((
        "8. Kode Kelas LULC (Selain 0)",
        cls_fn(meta1),
        cls_fn(meta2),
        val_t3(cls_fn),
        f"OK ({len(cls_sets[0])} kelas aktif identik)" if cls_same else "PERLU SINKRONISASI LEGENDA: Daftar kelas disamakan di .rdc",
    ))

    return rows


def compare_t1_t2_for_lcm(meta1: Dict, meta2: Dict) -> List[Tuple[str, str, str, str]]:
    """Kompatibilitas mundur untuk 2 peta LULC."""
    return [(p, v1, v2, st) for (p, v1, v2, _, st) in compare_lulc_metadata_for_lcm(meta1, meta2, None)]


def audit_driver_against_lulc(drv_meta: Dict, ref_meta: Optional[Dict]) -> Tuple[str, List[str]]:
    """
    Memeriksa metadata satu file Variabel Pendorong (Driver Variable) dan
    membandingkannya langsung dengan metadata Peta LULC Acuan (T1).
    Mengembalikan:
      (status_ringkas_untuk_tabel, daftar_rincian_diagnosis)
    """
    details: List[str] = []
    issues: List[str] = []

    nd_str = f"{drv_meta['nodata']:.4g}" if isinstance(drv_meta["nodata"], float) else str(drv_meta["nodata"])
    details.append(
        f"File Faktor : {drv_meta['name']} | Tipe Asli: {drv_meta['dtype']} | "
        f"CRS: {drv_meta['crs_display']} ({drv_meta['ref_system']}, {drv_meta['ref_units']})"
    )
    details.append(
        f"  - Dimensi & Resolusi : {drv_meta['width']} kol x {drv_meta['height']} bar | "
        f"Resolusi: {drv_meta['res_x']:.5g} x {drv_meta['res_y']:.5g}"
    )
    details.append(
        f"  - Batas Koordinat    : minX={drv_meta['min_x']:.3f}, maxX={drv_meta['max_x']:.3f}, "
        f"minY={drv_meta['min_y']:.3f}, maxY={drv_meta['max_y']:.3f}"
    )
    details.append(
        f"  - Rentang Nilai      : {drv_meta['min_val']:.4f} s/d {drv_meta['max_val']:.4f} | "
        f"NoData Asli: {nd_str} ({drv_meta['nodata_count']:,} piksel)"
    )

    if not drv_meta["crs_wkt"]:
        issues.append("CRS belum terdefinisi")
    elif not drv_meta["is_projected"]:
        issues.append("CRS masih derajat (akan direproyeksi ke UTM)")

    if drv_meta["nodata"] is not None and drv_meta["nodata"] != 0:
        issues.append("NoData ekstrem/bukan 0 (akan diubah ke 0)")

    if ref_meta is None:
        status_short = "Siap (Klik '1. Cek & Bandingkan Metadata' untuk cek vs LULC T1)"
        details.append(f"  - Status vs LULC T1  : [BELUM DIBANDINGKAN - Pilih LULC T1 lalu klik Cek Metadata]")
        return status_short, details

    # Bandingkan terhadap LULC T1
    crs_match = (drv_meta["epsg"] == ref_meta["epsg"]) and (drv_meta["ref_system"] == ref_meta["ref_system"])
    dim_match = (drv_meta["width"] == ref_meta["width"]) and (drv_meta["height"] == ref_meta["height"])
    res_match = np.isclose(drv_meta["res_x"], ref_meta["res_x"], atol=1e-5) and np.isclose(
        drv_meta["res_y"], ref_meta["res_y"], atol=1e-5
    )
    ext_match = (
        np.isclose(drv_meta["min_x"], ref_meta["min_x"], atol=1e-3)
        and np.isclose(drv_meta["max_x"], ref_meta["max_x"], atol=1e-3)
        and np.isclose(drv_meta["min_y"], ref_meta["min_y"], atol=1e-3)
        and np.isclose(drv_meta["max_y"], ref_meta["max_y"], atol=1e-3)
    )

    if not crs_match:
        issues.append(f"CRS beda dgn T1 ({drv_meta['crs_display']} vs {ref_meta['crs_display']})")
    if not dim_match:
        issues.append(f"Dimensi beda ({drv_meta['width']}x{drv_meta['height']} vs {ref_meta['width']}x{ref_meta['height']})")
    if not res_match:
        issues.append("Resolusi beda dgn T1")
    if not ext_match:
        issues.append("Batas Extent bergeser dari T1")

    if crs_match and dim_match and res_match and ext_match:
        if not issues:
            status_short = "OK (Geometri 100% Cocok dgn LULC T1)"
        else:
            status_short = "Geometri Cocok (" + ", ".join(issues) + ")"
    else:
        status_short = "PERLU ALIGNMENT (" + ", ".join(issues) + ")"

    details.append(f"  - Status vs LULC T1  : {status_short}")
    return status_short, details


# ==============================================================================
# 4. FUNGSI REPROYEKSI, SPATIAL ALIGNMENT & KONVERSI .RST + .RDC
# ==============================================================================

def compute_unified_grid(
    meta1: Dict,
    meta2: Dict,
    target_crs_input: str,
    target_res: float,
    extent_mode: str,
    meta3: Optional[Dict] = None,
) -> Tuple[str, str, str, float, float, float, float, int, int]:
    """
    Menghitung grid target bersama (Target WKT, ref_sys, ref_unit, min_x, min_y,
    max_x, max_y, cols, rows) untuk T1, T2, (opsional) T3, dan Driver Variables.
    """
    _, _, target_wkt, ref_sys, ref_unit = parse_crs_info(target_crs_input)

    def transform_bounds_to_target(meta: Dict) -> Tuple[float, float, float, float]:
        src_wkt = meta["crs_wkt"] if meta["crs_wkt"] else target_wkt
        if src_wkt == target_wkt:
            return meta["min_x"], meta["min_y"], meta["max_x"], meta["max_y"]

        if HAS_GDAL:
            src_srs = osr.SpatialReference()
            src_srs.ImportFromWkt(src_wkt)
            src_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

            dst_srs = osr.SpatialReference()
            dst_srs.ImportFromWkt(target_wkt)
            dst_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

            ct = osr.CoordinateTransformation(src_srs, dst_srs)
            corners = [
                (meta["min_x"], meta["min_y"]),
                (meta["min_x"], meta["max_y"]),
                (meta["max_x"], meta["min_y"]),
                (meta["max_x"], meta["max_y"]),
            ]
            xs, ys = [], []
            for x, y in corners:
                tx, ty, _ = ct.TransformPoint(x, y)
                xs.append(tx)
                ys.append(ty)
            return float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))
        else:
            transform, w, h = calculate_default_transform(
                RioCRS.from_wkt(src_wkt),
                RioCRS.from_wkt(target_wkt),
                meta["width"],
                meta["height"],
                meta["min_x"],
                meta["min_y"],
                meta["max_x"],
                meta["max_y"],
            )
            min_x = float(transform.c)
            max_y = float(transform.f)
            max_x = min_x + w * float(transform.a)
            min_y = max_y + h * float(transform.e)
            return min_x, min_y, max_x, max_y

    metas = [meta1, meta2] + ([meta3] if meta3 is not None else [])
    bounds_list = [transform_bounds_to_target(m) for m in metas]

    if extent_mode.startswith("T1"):
        min_x, min_y, max_x, max_y = bounds_list[0]
    elif extent_mode.startswith("T2"):
        min_x, min_y, max_x, max_y = bounds_list[1]
    elif extent_mode.startswith("T3") and len(bounds_list) >= 3:
        min_x, min_y, max_x, max_y = bounds_list[2]
    elif extent_mode.startswith("Intersection"):
        min_x = max(b[0] for b in bounds_list)
        min_y = max(b[1] for b in bounds_list)
        max_x = min(b[2] for b in bounds_list)
        max_y = min(b[3] for b in bounds_list)
        if min_x >= max_x or min_y >= max_y:
            raise ValueError("Area peta tidak saling bertampalan (Intersection kosong)!")
    else:  # Union
        min_x = min(b[0] for b in bounds_list)
        min_y = min(b[1] for b in bounds_list)
        max_x = max(b[2] for b in bounds_list)
        max_y = max(b[3] for b in bounds_list)

    cols = max(1, int(round((max_x - min_x) / target_res)))
    rows = max(1, int(round((max_y - min_y) / target_res)))
    max_x_aligned = min_x + cols * target_res
    min_y_aligned = max_y - rows * target_res

    return target_wkt, ref_sys, ref_unit, min_x, min_y_aligned, max_x_aligned, max_y, cols, rows


def align_and_reclass_raster(
    tif_path: str,
    src_wkt_fallback: str,
    target_wkt: str,
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    cols: int,
    rows: int,
    target_res: float,
    flag_val: int,
    reclass_map: Dict[int, int],
) -> np.ndarray:
    """
    Mereproyeksi dan menyelaraskan (resample Nearest Neighbor) satu file .tif LULC
    ke grid target bersama, menangani NoData dengan aman, lalu melakukan Reclassify.
    """
    internal_nodata = -999999

    if HAS_GDAL:
        src_ds = gdal.Open(str(tif_path), gdal.GA_ReadOnly)
        band = src_ds.GetRasterBand(1)
        src_arr = band.ReadAsArray()
        src_nodata = band.GetNoDataValue()
        src_gt = src_ds.GetGeoTransform()
        src_proj = src_ds.GetProjection() or src_wkt_fallback
        src_ds = None

        if np.issubdtype(src_arr.dtype, np.floating):
            nan_mask = np.isnan(src_arr)
            if src_nodata is not None and not np.isnan(src_nodata):
                nan_mask = nan_mask | np.isclose(src_arr, src_nodata)
            clean_src = np.where(nan_mask, internal_nodata, np.round(src_arr)).astype(np.int32)
        else:
            clean_src = src_arr.astype(np.int32)
            if src_nodata is not None:
                clean_src[clean_src == int(round(src_nodata))] = internal_nodata

        mem_drv = gdal.GetDriverByName("MEM")
        src_mem = mem_drv.Create("", clean_src.shape[1], clean_src.shape[0], 1, gdal.GDT_Int32)
        src_mem.SetGeoTransform(src_gt)
        src_mem.SetProjection(src_proj)
        src_mem_band = src_mem.GetRasterBand(1)
        src_mem_band.SetNoDataValue(float(internal_nodata))
        src_mem_band.WriteArray(clean_src)

        dst_mem = mem_drv.Create("", cols, rows, 1, gdal.GDT_Int32)
        dst_gt = (min_x, target_res, 0.0, max_y, 0.0, -target_res)
        dst_mem.SetGeoTransform(dst_gt)
        dst_mem.SetProjection(target_wkt)
        dst_mem_band = dst_mem.GetRasterBand(1)
        dst_mem_band.SetNoDataValue(float(internal_nodata))
        dst_mem_band.Fill(float(internal_nodata))

        gdal.ReprojectImage(
            src_mem,
            dst_mem,
            src_proj,
            target_wkt,
            gdal.GRA_NearestNeighbour,
        )
        dst_arr = dst_mem.GetRasterBand(1).ReadAsArray().astype(np.int32)
        src_mem = None
        dst_mem = None

    elif HAS_RASTERIO:
        with rasterio.open(tif_path) as src:
            src_arr = src.read(1)
            src_crs = src.crs if src.crs else RioCRS.from_wkt(src_wkt_fallback)
            src_nodata = src.nodata

            if np.issubdtype(src_arr.dtype, np.floating):
                nan_mask = np.isnan(src_arr)
                if src_nodata is not None and not np.isnan(src_nodata):
                    nan_mask = nan_mask | np.isclose(src_arr, src_nodata)
                clean_src = np.where(nan_mask, internal_nodata, np.round(src_arr)).astype(np.int32)
            else:
                clean_src = src_arr.astype(np.int32)
                if src_nodata is not None:
                    clean_src[clean_src == int(round(src_nodata))] = internal_nodata

            dst_arr = np.full((rows, cols), internal_nodata, dtype=np.int32)
            dst_transform = rio_from_bounds(min_x, min_y, max_x, max_y, cols, rows)

            rio_reproject(
                source=clean_src,
                destination=dst_arr,
                src_transform=src.transform,
                src_crs=src_crs,
                src_nodata=internal_nodata,
                dst_transform=dst_transform,
                dst_crs=RioCRS.from_wkt(target_wkt),
                dst_nodata=internal_nodata,
                resampling=RioResampling.nearest,
            )
    else:
        raise RuntimeError("Pustaka GDAL atau Rasterio belum tersedia.")

    final_arr = np.full((rows, cols), flag_val, dtype=np.int32)
    for old_code, new_code in reclass_map.items():
        final_arr[dst_arr == old_code] = new_code

    unmapped_valid = ~np.isin(dst_arr, list(reclass_map.keys()) + [internal_nodata])
    final_arr[unmapped_valid] = dst_arr[unmapped_valid]

    return final_arr


def align_driver_raster(
    tif_path: str,
    src_wkt_fallback: str,
    target_wkt: str,
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    cols: int,
    rows: int,
    target_res: float,
    resampling_method: str,
    flag_val: float,
    common_bg_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Mereproyeksi dan menyelaraskan peta Variabel Pendorong (Driver Variable,
    seperti DEM, Kemiringan Lereng, Jarak dari Jalan) ke grid yang 100% identik
    dengan peta LULC.

    Konsep Metodologi GIS:
    - Data kontinu (DEM, Lereng, Jarak) wajib di-resample dengan metode
      'bilinear' atau 'cubic' agar tidak muncul artefak patahan tangga (stair-step).
    - Data pendorong kategorikal (misal Jenis Tanah / Zonasi) menggunakan 'nearest'.
    """
    internal_nodata = -999999.0
    method_key = resampling_method.lower()

    if HAS_GDAL:
        if "cubic" in method_key:
            gdal_alg = gdal.GRA_Cubic
        elif "nearest" in method_key:
            gdal_alg = gdal.GRA_NearestNeighbour
        else:
            gdal_alg = gdal.GRA_Bilinear

        src_ds = gdal.Open(str(tif_path), gdal.GA_ReadOnly)
        band = src_ds.GetRasterBand(1)
        src_arr = band.ReadAsArray().astype(np.float32)
        src_nodata = band.GetNoDataValue()
        src_gt = src_ds.GetGeoTransform()
        src_proj = src_ds.GetProjection() or src_wkt_fallback
        src_ds = None

        src_arr64 = src_arr.astype(np.float64)
        nan_mask = np.isnan(src_arr64) | (src_arr64 <= -1e30) | (src_arr64 >= 1e30)
        if src_nodata is not None and not np.isnan(src_nodata):
            nd_f = float(src_nodata)
            if abs(nd_f) <= 1e30:
                nan_mask = nan_mask | np.isclose(src_arr64, nd_f, rtol=1e-5, atol=1e-7)
        clean_src = np.where(nan_mask, internal_nodata, src_arr).astype(np.float32)

        mem_drv = gdal.GetDriverByName("MEM")
        src_mem = mem_drv.Create("", clean_src.shape[1], clean_src.shape[0], 1, gdal.GDT_Float32)
        src_mem.SetGeoTransform(src_gt)
        src_mem.SetProjection(src_proj)
        src_mem_band = src_mem.GetRasterBand(1)
        src_mem_band.SetNoDataValue(float(internal_nodata))
        src_mem_band.WriteArray(clean_src)

        dst_mem = mem_drv.Create("", cols, rows, 1, gdal.GDT_Float32)
        dst_gt = (min_x, target_res, 0.0, max_y, 0.0, -target_res)
        dst_mem.SetGeoTransform(dst_gt)
        dst_mem.SetProjection(target_wkt)
        dst_mem_band = dst_mem.GetRasterBand(1)
        dst_mem_band.SetNoDataValue(float(internal_nodata))
        dst_mem_band.Fill(float(internal_nodata))

        gdal.ReprojectImage(src_mem, dst_mem, src_proj, target_wkt, gdal_alg)
        dst_arr = dst_mem.GetRasterBand(1).ReadAsArray().astype(np.float32)
        src_mem = None
        dst_mem = None

    elif HAS_RASTERIO:
        if "cubic" in method_key:
            rio_alg = RioResampling.cubic
        elif "nearest" in method_key:
            rio_alg = RioResampling.nearest
        else:
            rio_alg = RioResampling.bilinear

        with rasterio.open(tif_path) as src:
            src_arr = src.read(1).astype(np.float32)
            src_crs = src.crs if src.crs else RioCRS.from_wkt(src_wkt_fallback)
            src_nodata = src.nodata

            src_arr64 = src_arr.astype(np.float64)
            nan_mask = np.isnan(src_arr64) | (src_arr64 <= -1e30) | (src_arr64 >= 1e30)
            if src_nodata is not None and not np.isnan(src_nodata):
                nd_f = float(src_nodata)
                if abs(nd_f) <= 1e30:
                    nan_mask = nan_mask | np.isclose(src_arr64, nd_f, rtol=1e-5, atol=1e-7)
            clean_src = np.where(nan_mask, internal_nodata, src_arr).astype(np.float32)

            dst_arr = np.full((rows, cols), internal_nodata, dtype=np.float32)
            dst_transform = rio_from_bounds(min_x, min_y, max_x, max_y, cols, rows)

            rio_reproject(
                source=clean_src,
                destination=dst_arr,
                src_transform=src.transform,
                src_crs=src_crs,
                src_nodata=internal_nodata,
                dst_transform=dst_transform,
                dst_crs=RioCRS.from_wkt(target_wkt),
                dst_nodata=internal_nodata,
                resampling=rio_alg,
            )
    else:
        raise RuntimeError("Pustaka GDAL atau Rasterio belum tersedia.")

    # Ganti internal_nodata dan NaN dengan flag_val
    nodata_out_mask = np.isnan(dst_arr) | np.isclose(dst_arr, internal_nodata)
    dst_arr[nodata_out_mask] = float(flag_val)

    # Sinkronkan dengan masker background LULC jika diminta
    if common_bg_mask is not None:
        dst_arr[common_bg_mask] = float(flag_val)

    return dst_arr


def save_geotiff(
    tif_path: Path,
    array_2d: np.ndarray,
    target_wkt: str,
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    target_res: float,
    dtype_terrset: str,
    nodata_val: float,
):
    """
    Menyimpan hasil penyelarasan ke file GeoTIFF (.tif) sebagai cadangan/verifikasi di QGIS.
    """
    rows, cols = array_2d.shape
    if HAS_GDAL:
        drv = gdal.GetDriverByName("GTiff")
        if dtype_terrset == "byte":
            gdal_dtype, np_dtype = gdal.GDT_Byte, np.uint8
        elif dtype_terrset == "integer":
            gdal_dtype, np_dtype = gdal.GDT_Int16, np.int16
        else:
            gdal_dtype, np_dtype = gdal.GDT_Float32, np.float32

        ds = drv.Create(str(tif_path), cols, rows, 1, gdal_dtype)
        ds.SetGeoTransform((min_x, target_res, 0.0, max_y, 0.0, -target_res))
        ds.SetProjection(target_wkt)
        band = ds.GetRasterBand(1)
        band.SetNoDataValue(float(nodata_val))
        band.WriteArray(array_2d.astype(np_dtype))
        band.FlushCache()
        ds = None
    elif HAS_RASTERIO:
        if dtype_terrset == "byte":
            rio_dtype = "uint8"
        elif dtype_terrset == "integer":
            rio_dtype = "int16"
        else:
            rio_dtype = "float32"
        transform = rio_from_bounds(min_x, min_y, max_x, max_y, cols, rows)
        with rasterio.open(
            tif_path,
            "w",
            driver="GTiff",
            height=rows,
            width=cols,
            count=1,
            dtype=rio_dtype,
            crs=RioCRS.from_wkt(target_wkt),
            transform=transform,
            nodata=nodata_val,
        ) as dst:
            dst.write(array_2d.astype(rio_dtype), 1)


def write_idrisi_rst_rdc(
    output_base_path: Path,
    array_2d: np.ndarray,
    title: str,
    data_type_terrset: str,
    ref_system: str,
    ref_units: str,
    min_x: float,
    max_x: float,
    min_y: float,
    max_y: float,
    resolution: float,
    flag_value: float,
    flag_defn: str,
    value_units: str = "classes",
    legend_classes: Optional[Dict[int, str]] = None,
    forced_min_val: Optional[float] = None,
    forced_max_val: Optional[float] = None,
    valid_mask_override: Optional[np.ndarray] = None,
) -> Tuple[Path, Path]:
    """
    Menulis pasangan file native TerrSet / IDRISI:
    1. File .rst (flat binary file tanpa header, urutan baris Utara -> Selatan)
    2. File .rdc (Raster Documentation File dengan format 12-karakter key + ': ')
    """
    rst_path = output_base_path.with_suffix(".rst")
    rdc_path = output_base_path.with_suffix(".rdc")

    rows, cols = array_2d.shape

    if data_type_terrset == "byte":
        out_arr = np.clip(np.round(array_2d), 0, 255).astype(np.uint8)
    elif data_type_terrset == "integer":
        out_arr = np.clip(np.round(array_2d), -32768, 32767).astype("<i2")
    elif data_type_terrset == "real":
        out_arr = array_2d.astype("<f4")
    else:
        raise ValueError(f"Tipe data TerrSet tidak dikenal: {data_type_terrset}")

    with open(rst_path, "wb") as f_rst:
        f_rst.write(out_arr.tobytes(order="C"))

    if forced_min_val is not None and forced_max_val is not None:
        min_val = forced_min_val
        max_val = forced_max_val
    else:
        if valid_mask_override is not None and np.any(valid_mask_override):
            valid_mask = valid_mask_override
        else:
            valid_mask = ~np.isclose(out_arr.astype(np.float64), float(flag_value))
        if np.any(valid_mask):
            min_val = float(np.min(out_arr[valid_mask]))
            max_val = float(np.max(out_arr[valid_mask]))
        else:
            min_val = 0.0
            max_val = 0.0

    if data_type_terrset in ("byte", "integer"):
        min_val_str = f"{int(round(min_val))}"
        max_val_str = f"{int(round(max_val))}"
        flag_val_str = f"{int(round(flag_value))}"
    else:
        min_val_str = f"{min_val:.7f}"
        max_val_str = f"{max_val:.7f}"
        flag_val_str = f"{flag_value:.7f}"

    legend_cats = len(legend_classes) if legend_classes else 0

    rdc_lines = [
        f"{'file format':<12}: IDRISI Raster A.1",
        f"{'file title':<12}: {title}",
        f"{'data type':<12}: {data_type_terrset}",
        f"{'file type':<12}: binary",
        f"{'columns':<12}: {cols}",
        f"{'rows':<12}: {rows}",
        f"{'ref. system':<12}: {ref_system}",
        f"{'ref. units':<12}: {ref_units}",
        f"{'unit dist.':<12}: 1.0000000",
        f"{'min. X':<12}: {min_x:.7f}",
        f"{'max. X':<12}: {max_x:.7f}",
        f"{'min. Y':<12}: {min_y:.7f}",
        f"{'max. Y':<12}: {max_y:.7f}",
        f"{'pos' + chr(39) + 'n error':<12}: unknown",
        f"{'resolution':<12}: {resolution:.7f}",
        f"{'min. value':<12}: {min_val_str}",
        f"{'max. value':<12}: {max_val_str}",
        f"{'display min':<12}: {min_val_str}",
        f"{'display max':<12}: {max_val_str}",
        f"{'value units':<12}: {value_units}",
        f"{'value error':<12}: unknown",
        f"{'flag value':<12}: {flag_val_str}",
        f"{'flag def' + chr(39) + 'n':<12}: {flag_defn}",
        f"{'legend cats':<12}: {legend_cats}",
    ]

    if legend_classes and legend_cats > 0:
        for code_num in sorted(legend_classes.keys()):
            label = legend_classes[code_num]
            key_str = f"code{code_num:7d} "
            rdc_lines.append(f"{key_str}: {label}")

    with open(rdc_path, "w", encoding="ascii", errors="replace", newline="\r\n") as f_rdc:
        f_rdc.write("\n".join(rdc_lines) + "\n")

    return rst_path, rdc_path


def create_sample_lulc_tifs(sample_dir: Path) -> Tuple[Path, Path, Path, List[Path]]:
    """
    Membuat paket data sampel GeoTIFF (.tif) untuk simulasi lengkap LCM TerrSet:
    - Sample_LULC_2015.tif (T1)
    - Sample_LULC_2020.tif (T2)
    - Sample_LULC_2025_Aktual.tif (T3 - untuk validasi prediksi)
    - Sample_Driver_DEM.tif & Sample_Driver_Jarak_Jalan.tif (Variabel Pendorong)
    """
    sample_dir.mkdir(parents=True, exist_ok=True)
    t1_path = sample_dir / "Sample_LULC_2015.tif"
    t2_path = sample_dir / "Sample_LULC_2020.tif"
    t3_path = sample_dir / "Sample_LULC_2025_Aktual.tif"
    dem_path = sample_dir / "Sample_Driver_DEM_Elevasi.tif"
    road_path = sample_dir / "Sample_Driver_Jarak_Jalan.tif"

    np.random.seed(42)
    _, _, target_wkt, _, _ = parse_crs_info("EPSG:32749")

    # T1 (2015): 100 x 100 piksel
    rows1, cols1 = 100, 100
    min_x1, min_y1 = 430000.0, 9140000.0
    res = 30.0
    max_x1 = min_x1 + cols1 * res
    max_y1 = min_y1 + rows1 * res

    yy1, xx1 = np.mgrid[0:rows1, 0:cols1]
    arr1 = np.ones((rows1, cols1), dtype=np.uint8)
    arr1[(yy1 > 35) & (yy1 < 85)] = 2
    arr1[(xx1 > 40) & (xx1 < 70) & (yy1 > 45) & (yy1 < 75)] = 3
    arr1[(xx1 > 15) & (xx1 < 25)] = 4
    arr1[(xx1 > 75) & (yy1 > 70)] = 5
    arr1[:5, :5] = 255
    save_geotiff(t1_path, arr1, target_wkt, min_x1, min_y1, max_x1, max_y1, res, "byte", 255)

    # T2 (2020): 102 x 101 piksel (sengaja dibuat beda ukuran sedikit)
    rows2, cols2 = 102, 101
    min_x2, min_y2 = 430000.0, 9139940.0
    max_x2 = min_x2 + cols2 * res
    max_y2 = min_y2 + rows2 * res

    yy2, xx2 = np.mgrid[0:rows2, 0:cols2]
    arr2 = np.ones((rows2, cols2), dtype=np.uint8)
    arr2[:rows1, :cols1] = arr1
    arr2[(xx2 > 32) & (xx2 < 78) & (yy2 > 38) & (yy2 < 80)] = 3
    arr2[(xx2 > 15) & (xx2 < 25)] = 4
    arr2[:5, :5] = 255
    save_geotiff(t2_path, arr2, target_wkt, min_x2, min_y2, max_x2, max_y2, res, "byte", 255)

    # T3 (2025 Aktual): 101 x 100 piksel (ekspansi lahan terbangun lebih lanjut)
    rows3, cols3 = 101, 100
    min_x3, min_y3 = 430000.0, 9139970.0
    max_x3 = min_x3 + cols3 * res
    max_y3 = min_y3 + rows3 * res

    yy3, xx3 = np.mgrid[0:rows3, 0:cols3]
    arr3 = np.ones((rows3, cols3), dtype=np.uint8)
    arr3[:rows1, :cols1] = arr2[:rows1, :cols1]
    arr3[(xx3 > 27) & (xx3 < 84) & (yy3 > 32) & (yy3 < 84)] = 3
    arr3[(xx3 > 15) & (xx3 < 25)] = 4
    arr3[:5, :5] = 255
    save_geotiff(t3_path, arr3, target_wkt, min_x3, min_y3, max_x3, max_y3, res, "byte", 255)

    # Variabel Pendorong 1: DEM / Elevasi (float32, 50m - 450m mdpl)
    dem_arr = (50.0 + (rows1 - yy1) * 3.2 + np.sin(xx1 / 10.0) * 25.0).astype(np.float32)
    dem_arr[:5, :5] = -9999.0
    save_geotiff(dem_path, dem_arr, target_wkt, min_x1, min_y1, max_x1, max_y1, res, "real", -9999.0)

    # Variabel Pendorong 2: Jarak dari Jalan Utama (float32, meter)
    dist_arr = (np.abs(yy1 - 60.0) * res).astype(np.float32)
    dist_arr[:5, :5] = -9999.0
    save_geotiff(road_path, dist_arr, target_wkt, min_x1, min_y1, max_x1, max_y1, res, "real", -9999.0)

    return t1_path, t2_path, t3_path, [dem_path, road_path]
