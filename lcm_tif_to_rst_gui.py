"""
================================================================================
TERRSET LCM STUDIO — VALIDATOR, ALIGNER & .RST/.RDC CONVERTER (PyQt5 GUI v2.1)
================================================================================
Dibuat khusus untuk: Vinaryama (Mahasiswa Geografi - GIS & Remote Sensing)

Pembaruan v2.1 (Minimalist & Modern GIS UI/UX):
- Desain antarmuka bersih, minimalis, dan modern menggunakan Qt StyleSheet (QSS)
  dengan palet warna Slate & Emerald yang nyaman di mata.
- Mendukung hingga 3 Peta LULC (T1, T2, dan T3 Aktual/Validasi).
- Pemilihan & Auto-Detect Zona UTM Indonesia + konversi resolusi derajat -> meter.
- Tab khusus Variabel Pendorong (Driver Variables) dengan audit otomatis.
- Perhitungan luas perubahan lahan (ha, km², %) otomatis + ekspor ke CSV (Excel).
================================================================================
"""

import csv
from pathlib import Path
import sys
from typing import Dict, List, Optional
import numpy as np

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from terrset_lcm_core import (
    DEFAULT_CLASS_NAMES,
    HAS_GDAL,
    HAS_RASTERIO,
    UTM_PRESETS_INDONESIA,
    align_and_reclass_raster,
    align_driver_raster,
    audit_driver_against_lulc,
    compare_lulc_metadata_for_lcm,
    compute_unified_grid,
    create_sample_lulc_tifs,
    inspect_raster_metadata,
    parse_crs_info,
    save_geotiff,
    suggest_utm_from_metadata,
    write_idrisi_rst_rdc,
)


# ==============================================================================
# TEMA VISUAL MINIMALIS & MODERN (QSS STYLESHEET)
# ==============================================================================

MODERN_GIS_STYLESHEET = """
QMainWindow, QWidget#CentralWidget {
    background-color: #F8FAFC;
    color: #0F172A;
    font-family: "Segoe UI", sans-serif;
    font-size: 9.5pt;
}

/* Header Banner */
QFrame#HeaderCard {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
}
QLabel#AppTitle {
    color: #0F172A;
    font-size: 13pt;
    font-weight: bold;
}
QLabel#AppSubtitle {
    color: #64748B;
    font-size: 9pt;
}
QLabel#EngineBadge {
    background-color: #EFF6FF;
    color: #1D4ED8;
    border: 1px solid #BFDBFE;
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 8.5pt;
    font-weight: bold;
}

/* GroupBox (Cards) */
QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    margin-top: 10px;
    padding: 12px 10px 10px 10px;
    font-weight: bold;
    color: #1E293B;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #334155;
    background-color: #FFFFFF;
}

/* Input Fields */
QLineEdit, QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 5px 10px;
    color: #0F172A;
    min-height: 20px;
}
QLineEdit:focus, QComboBox:focus {
    border: 1.5px solid #2563EB;
    background-color: #FFFFFF;
}
QLineEdit:disabled, QComboBox:disabled {
    background-color: #F1F5F9;
    color: #94A3B8;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}

/* Buttons */
QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 6px 14px;
    color: #334155;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #F1F5F9;
    border-color: #94A3B8;
    color: #0F172A;
}
QPushButton:pressed {
    background-color: #E2E8F0;
}

/* Primary Button (Audit / Blue) */
QPushButton#PrimaryBlueBtn {
    background-color: #2563EB;
    border: 1px solid #1D4ED8;
    color: #FFFFFF;
    font-weight: bold;
    padding: 7px 16px;
}
QPushButton#PrimaryBlueBtn:hover {
    background-color: #1D4ED8;
}

/* Primary Action Button (Convert / Emerald Green) */
QPushButton#PrimaryGreenBtn {
    background-color: #059669;
    border: 1px solid #047857;
    color: #FFFFFF;
    font-weight: bold;
    padding: 7px 18px;
}
QPushButton#PrimaryGreenBtn:hover {
    background-color: #047857;
}

/* Accent Subtle Button */
QPushButton#SoftBlueBtn {
    background-color: #EFF6FF;
    border: 1px solid #BFDBFE;
    color: #1D4ED8;
    font-weight: 600;
}
QPushButton#SoftBlueBtn:hover {
    background-color: #DBEAFE;
}

/* Tabs */
QTabWidget::pane {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background-color: #F1F5F9;
    border: 1px solid #E2E8F0;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 18px;
    margin-right: 4px;
    color: #64748B;
    font-weight: 600;
}
QTabBar::tab:hover {
    background-color: #E2E8F0;
    color: #1E293B;
}
QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #2563EB;
    border-bottom: 2px solid #2563EB;
    font-weight: bold;
}

/* Tables */
QTableWidget {
    background-color: #FFFFFF;
    alternate-background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    gridline-color: #F1F5F9;
    selection-background-color: #EFF6FF;
    selection-color: #1E3A8A;
}
QHeaderView::section {
    background-color: #F8FAFC;
    color: #475569;
    font-weight: bold;
    border: none;
    border-bottom: 1px solid #E2E8F0;
    border-right: 1px solid #F1F5F9;
    padding: 7px 10px;
}

/* Log & Summary Text Boxes */
QPlainTextEdit {
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 8px;
    color: #1E293B;
}

/* CheckBox */
QCheckBox {
    color: #334155;
    spacing: 6px;
}
"""


class TerrSetLCMConverterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.engine_name = "OSGeo GDAL" if HAS_GDAL else ("Rasterio" if HAS_RASTERIO else "No Engine")
        self.setWindowTitle("TerrSet LCM Studio — Validator, Spatial Aligner & .RST Converter (Vinaryama GIS)")
        self.resize(1200, 820)
        self.setMinimumSize(1020, 700)

        self.meta_t1: Optional[Dict] = None
        self.meta_t2: Optional[Dict] = None
        self.meta_t3: Optional[Dict] = None
        self.driver_metas: List[Dict] = []
        self.last_area_csv_rows: List[List] = []

        self.base_dir = Path(__file__).resolve().parent
        self._init_ui()

    # ==========================================================================
    # 1. ANTARMUKA PENGGUNA MINIMALIS & MODERN (UI/UX)
    # ==========================================================================

    def _init_ui(self):
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(10)

        # 1. Header Banner Minimalis
        header_card = QFrame()
        header_card.setObjectName("HeaderCard")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(16, 10, 16, 10)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel("TerrSet LCM Studio")
        title_lbl.setObjectName("AppTitle")
        title_col.addWidget(title_lbl)

        subtitle_lbl = QLabel(
            "Validasi Metadata  •  Standardisasi Proyeksi UTM & Grid  •  Sinkronisasi Legenda & Faktor  •  Konversi .TIF ke .RST/.RDC"
        )
        subtitle_lbl.setObjectName("AppSubtitle")
        title_col.addWidget(subtitle_lbl)
        header_layout.addLayout(title_col)

        header_layout.addStretch()

        badge_lbl = QLabel(f"Engine: {self.engine_name}")
        badge_lbl.setObjectName("EngineBadge")
        header_layout.addWidget(badge_lbl, alignment=Qt.AlignRight | Qt.AlignVCenter)
        main_layout.addWidget(header_card)

        # 2. Kartu Input Data Utama (Compact Grid)
        input_group = QGroupBox("Input Data Tutupan Lahan (.tif) && Direktori Output")
        grid = QGridLayout(input_group)
        grid.setContentsMargins(12, 14, 12, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        # T1
        lbl_t1 = QLabel("LULC T1 (Tahun Awal):")
        lbl_t1.setMinimumWidth(165)
        grid.addWidget(lbl_t1, 0, 0)
        self.t1_edit = QLineEdit()
        self.t1_edit.setPlaceholderText("Pilih file GeoTIFF LULC Tahun Awal (misal 2015)...")
        grid.addWidget(self.t1_edit, 0, 1)
        btn_t1 = QPushButton("Pilih File...")
        btn_t1.setFixedWidth(110)
        btn_t1.clicked.connect(self._browse_t1)
        grid.addWidget(btn_t1, 0, 2)

        # T2
        grid.addWidget(QLabel("LULC T2 (Tahun Akhir):"), 1, 0)
        self.t2_edit = QLineEdit()
        self.t2_edit.setPlaceholderText("Pilih file GeoTIFF LULC Tahun Akhir (misal 2020)...")
        grid.addWidget(self.t2_edit, 1, 1)
        btn_t2 = QPushButton("Pilih File...")
        btn_t2.setFixedWidth(110)
        btn_t2.clicked.connect(self._browse_t2)
        grid.addWidget(btn_t2, 1, 2)

        # T3 (Opsional)
        self.use_t3_chk = QCheckBox("LULC T3 (Aktual / Validasi):")
        self.use_t3_chk.setChecked(False)
        self.use_t3_chk.toggled.connect(self._on_t3_toggled)
        grid.addWidget(self.use_t3_chk, 2, 0)

        self.t3_edit = QLineEdit()
        self.t3_edit.setPlaceholderText("Opsional — Pilih file GeoTIFF LULC Aktual (misal 2025) untuk validasi...")
        grid.addWidget(self.t3_edit, 2, 1)
        btn_t3 = QPushButton("Pilih File...")
        btn_t3.setFixedWidth(110)
        btn_t3.clicked.connect(self._browse_t3)
        grid.addWidget(btn_t3, 2, 2)

        # Folder Output
        grid.addWidget(QLabel("Folder Output (.rst/.rdc):"), 3, 0)
        self.out_dir_edit = QLineEdit(str(self.base_dir / "output_terrset_rst"))
        grid.addWidget(self.out_dir_edit, 3, 1)
        btn_out = QPushButton("Pilih Folder...")
        btn_out.setFixedWidth(110)
        btn_out.clicked.connect(self._browse_outdir)
        grid.addWidget(btn_out, 3, 2)

        # Baris Tombol Utama
        action_bar = QHBoxLayout()
        action_bar.setContentsMargins(0, 4, 0, 0)

        btn_sample = QPushButton("Muat Data Sampel Uji Coba")
        btn_sample.setToolTip("Buat otomatis sampel LULC 2015, 2020, 2025 + DEM & Jarak Jalan")
        btn_sample.clicked.connect(self._generate_sample_data)
        action_bar.addWidget(btn_sample)

        action_bar.addStretch()

        btn_check = QPushButton("1. Cek && Audit Metadata")
        btn_check.setObjectName("PrimaryBlueBtn")
        btn_check.clicked.connect(self.run_metadata_check)
        action_bar.addWidget(btn_check)

        btn_convert = QPushButton("2. Konversi Semua ke .RST + .RDC")
        btn_convert.setObjectName("PrimaryGreenBtn")
        btn_convert.clicked.connect(self.run_alignment_and_export)
        action_bar.addWidget(btn_convert)

        grid.addLayout(action_bar, 4, 0, 1, 3)
        main_layout.addWidget(input_group)

        # 3. Tab Navigasi Minimalis (4 Tab)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, stretch=1)

        self._build_tab_audit()
        self._build_tab_config()
        self._build_tab_drivers()
        self._build_tab_log()

    def _style_table(self, table: QTableWidget):
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(32)
        table.setShowGrid(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)

    def _build_tab_audit(self):
        self.tab_audit = QWidget()
        layout = QVBoxLayout(self.tab_audit)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self.table_audit = QTableWidget(0, 5)
        self._style_table(self.table_audit)
        self.table_audit.setHorizontalHeaderLabels([
            "Parameter Metadata",
            "LULC T1 (Awal)",
            "LULC T2 (Akhir)",
            "LULC T3 (Aktual)",
            "Status & Diagnosis LCM",
        ])
        header = self.table_audit.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.table_audit, stretch=3)

        lbl_diag = QLabel("Ringkasan Diagnosis & Rekomendasi:")
        lbl_diag.setStyleSheet("font-weight: bold; color: #334155;")
        layout.addWidget(lbl_diag)

        self.audit_summary_box = QPlainTextEdit()
        self.audit_summary_box.setReadOnly(True)
        self.audit_summary_box.setFont(QFont("Consolas", 9))
        self.audit_summary_box.setPlainText(
            "Pilih file GeoTIFF (.tif) di atas lalu klik '1. Cek & Audit Metadata', "
            "atau klik 'Muat Data Sampel Uji Coba' untuk simulasi."
        )
        layout.addWidget(self.audit_summary_box, stretch=2)

        self.tabs.addTab(self.tab_audit, "1. Audit Metadata")

    def _build_tab_config(self):
        self.tab_config = QWidget()
        layout = QVBoxLayout(self.tab_config)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        # Kartu Kiri: Sistem Koordinat & Grid Spasial
        spatial_group = QGroupBox("Sistem Koordinat (CRS) && Grid Spasial")
        s_grid = QGridLayout(spatial_group)
        s_grid.setContentsMargins(12, 14, 12, 10)
        s_grid.setHorizontalSpacing(8)
        s_grid.setVerticalSpacing(8)

        s_grid.addWidget(QLabel("Target CRS (UTM):"), 0, 0)
        self.target_crs_combo = QComboBox()
        self.target_crs_combo.setEditable(True)
        for display_text, epsg_code, _ in UTM_PRESETS_INDONESIA:
            self.target_crs_combo.addItem(display_text, epsg_code)
        self.target_crs_combo.setCurrentIndex(2)
        self.target_crs_combo.currentIndexChanged.connect(self._on_crs_preset_changed)
        s_grid.addWidget(self.target_crs_combo, 0, 1, 1, 2)

        crs_btn_row = QHBoxLayout()
        btn_auto_utm = QPushButton("Auto-Deteksi UTM dari Peta")
        btn_auto_utm.setObjectName("SoftBlueBtn")
        btn_auto_utm.clicked.connect(self._auto_detect_utm_from_raster)
        crs_btn_row.addWidget(btn_auto_utm)

        btn_sync_crs = QPushButton("Sinkronkan EPSG")
        btn_sync_crs.clicked.connect(self._sync_ref_system_from_epsg)
        crs_btn_row.addWidget(btn_sync_crs)
        s_grid.addLayout(crs_btn_row, 1, 1, 1, 2)

        s_grid.addWidget(QLabel("TerrSet ref. system:"), 2, 0)
        ref_layout = QHBoxLayout()
        self.ref_sys_edit = QLineEdit("utm-49s")
        ref_layout.addWidget(self.ref_sys_edit)
        ref_layout.addWidget(QLabel("Satuan:"))
        self.ref_unit_combo = QComboBox()
        self.ref_unit_combo.addItems(["m", "deg"])
        self.ref_unit_combo.setFixedWidth(70)
        ref_layout.addWidget(self.ref_unit_combo)
        s_grid.addLayout(ref_layout, 2, 1, 1, 2)

        s_grid.addWidget(QLabel("Acuan Batas Extent:"), 3, 0)
        self.extent_mode_combo = QComboBox()
        self.extent_mode_combo.addItems([
            "T1 (Ikuti Batas & Grid Peta Tahun Awal)",
            "T2 (Ikuti Batas & Grid Peta Tahun Akhir)",
            "T3 (Ikuti Batas & Grid Peta Tahun ke-3)",
            "Intersection (Irisan Area yang Bertampalan)",
            "Union (Gabungan Seluruh Area Peta)",
        ])
        s_grid.addWidget(self.extent_mode_combo, 3, 1, 1, 2)

        s_grid.addWidget(QLabel("Resolusi Target (m):"), 4, 0)
        self.target_res_edit = QLineEdit("30.0")
        s_grid.addWidget(self.target_res_edit, 4, 1)
        lbl_res_hint = QLabel("Piksel bujur sangkar (Nearest Neighbor)")
        lbl_res_hint.setStyleSheet("color: #64748B; font-size: 8.5pt;")
        s_grid.addWidget(lbl_res_hint, 4, 2)

        top_row.addWidget(spatial_group, stretch=1)

        # Kartu Kanan: Format Output .RST / .RDC
        rdc_group = QGroupBox("Pengaturan Output .RST / .RDC")
        r_grid = QGridLayout(rdc_group)
        r_grid.setContentsMargins(12, 14, 12, 10)
        r_grid.setHorizontalSpacing(8)
        r_grid.setVerticalSpacing(8)

        r_grid.addWidget(QLabel("Tipe Data & NoData:"), 0, 0)
        dt_nd_layout = QHBoxLayout()
        self.dtype_combo = QComboBox()
        self.dtype_combo.addItems(["byte", "integer"])
        self.dtype_combo.setFixedWidth(95)
        dt_nd_layout.addWidget(self.dtype_combo)
        dt_nd_layout.addWidget(QLabel("Background / NoData:"))
        self.flag_val_edit = QLineEdit("0")
        self.flag_val_edit.setFixedWidth(60)
        dt_nd_layout.addWidget(self.flag_val_edit)
        dt_nd_layout.addStretch()
        r_grid.addLayout(dt_nd_layout, 0, 1, 1, 2)

        r_grid.addWidget(QLabel("Output & Judul T1:"), 1, 0)
        self.t1_outname_edit = QLineEdit("LULC_2015_TerrSet")
        r_grid.addWidget(self.t1_outname_edit, 1, 1)
        self.t1_title_edit = QLineEdit("Tutupan Lahan 2015")
        r_grid.addWidget(self.t1_title_edit, 1, 2)

        r_grid.addWidget(QLabel("Output & Judul T2:"), 2, 0)
        self.t2_outname_edit = QLineEdit("LULC_2020_TerrSet")
        r_grid.addWidget(self.t2_outname_edit, 2, 1)
        self.t2_title_edit = QLineEdit("Tutupan Lahan 2020")
        r_grid.addWidget(self.t2_title_edit, 2, 2)

        r_grid.addWidget(QLabel("Output & Judul T3:"), 3, 0)
        self.t3_outname_edit = QLineEdit("LULC_2025_Aktual_TerrSet")
        self.t3_outname_edit.setEnabled(False)
        r_grid.addWidget(self.t3_outname_edit, 3, 1)
        self.t3_title_edit = QLineEdit("Tutupan Lahan 2025 Aktual")
        self.t3_title_edit.setEnabled(False)
        r_grid.addWidget(self.t3_title_edit, 3, 2)

        self.save_tif_chk = QCheckBox("Simpan juga salinan Aligned GeoTIFF (.tif) untuk verifikasi di QGIS")
        self.save_tif_chk.setChecked(True)
        r_grid.addWidget(self.save_tif_chk, 4, 0, 1, 3)

        top_row.addWidget(rdc_group, stretch=1)
        layout.addLayout(top_row)

        # Kartu Bawah: Editor Kelas & Legenda LULC
        legend_group = QGroupBox("Tabel Sinkronisasi Kode Kelas && Nama Legenda LULC (.rdc)")
        l_layout = QVBoxLayout(legend_group)
        l_layout.setContentsMargins(12, 14, 12, 10)
        l_layout.setSpacing(8)

        toolbar_row = QHBoxLayout()
        info_lbl = QLabel(
            "Nilai 0 digunakan sebagai Background/NoData. Kelas LULC dimulai dari 1, 2, 3... dan otomatis disamakan pada file .rdc T1, T2, dan T3."
        )
        info_lbl.setStyleSheet("color: #64748B;")
        toolbar_row.addWidget(info_lbl)
        toolbar_row.addStretch()

        btn_shift = QPushButton("Urutkan Kode 1..N")
        btn_shift.setObjectName("SoftBlueBtn")
        btn_shift.clicked.connect(self._auto_shift_codes_from_one)
        toolbar_row.addWidget(btn_shift)

        btn_reset = QPushButton("Reset Kode")
        btn_reset.clicked.connect(self._reset_class_codes)
        toolbar_row.addWidget(btn_reset)
        l_layout.addLayout(toolbar_row)

        self.table_legend = QTableWidget(0, 6)
        self._style_table(self.table_legend)
        self.table_legend.setHorizontalHeaderLabels([
            "Kode Asli (.tif)",
            "Piksel T1",
            "Piksel T2",
            "Piksel T3",
            "Kode Baru (.rst)",
            "Nama Kelas Legenda di .RDC (Klik untuk Edit)",
        ])
        l_header = self.table_legend.horizontalHeader()
        l_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        l_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        l_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        l_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        l_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        l_header.setSectionResizeMode(5, QHeaderView.Stretch)
        l_layout.addWidget(self.table_legend)

        layout.addWidget(legend_group, stretch=1)
        self.tabs.addTab(self.tab_config, "2. Proyeksi && Legenda")

    def _build_tab_drivers(self):
        self.tab_drivers = QWidget()
        layout = QVBoxLayout(self.tab_drivers)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        btn_bar = QHBoxLayout()
        btn_add_drv = QPushButton("+ Tambah Variabel Pendorong (.tif)")
        btn_add_drv.setObjectName("PrimaryBlueBtn")
        btn_add_drv.clicked.connect(self._add_driver_files)
        btn_bar.addWidget(btn_add_drv)

        btn_rem_drv = QPushButton("Hapus Baris")
        btn_rem_drv.clicked.connect(self._remove_selected_driver)
        btn_bar.addWidget(btn_rem_drv)

        btn_clr_drv = QPushButton("Bersihkan Semua")
        btn_clr_drv.clicked.connect(self._clear_all_drivers)
        btn_bar.addWidget(btn_clr_drv)

        btn_bar.addStretch()
        self.sync_driver_bg_chk = QCheckBox("Sinkronkan Background (0) dengan Masker LULC")
        self.sync_driver_bg_chk.setChecked(True)
        btn_bar.addWidget(self.sync_driver_bg_chk)
        layout.addLayout(btn_bar)

        self.table_drivers = QTableWidget(0, 9)
        self._style_table(self.table_drivers)
        self.table_drivers.setHorizontalHeaderLabels([
            "File Faktor (.tif)",
            "CRS & Dimensi",
            "Rentang Nilai",
            "Status vs LULC T1",
            "Metode Resampling",
            "Tipe Data",
            "Satuan (units)",
            "Nama Output (.rst)",
            "Judul Peta (.rdc)",
        ])
        d_header = self.table_drivers.horizontalHeader()
        d_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        d_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        d_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        d_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        d_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        d_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        d_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        d_header.setSectionResizeMode(7, QHeaderView.Stretch)
        d_header.setSectionResizeMode(8, QHeaderView.Stretch)
        layout.addWidget(self.table_drivers, stretch=3)

        lbl_drv_audit = QLabel("Rincian Audit Metadata Variabel Pendorong:")
        lbl_drv_audit.setStyleSheet("font-weight: bold; color: #334155;")
        layout.addWidget(lbl_drv_audit)

        self.driver_audit_box = QPlainTextEdit()
        self.driver_audit_box.setReadOnly(True)
        self.driver_audit_box.setFont(QFont("Consolas", 9))
        self.driver_audit_box.setPlainText(
            "Tambahkan file GeoTIFF (.tif) variabel pendorong seperti DEM, Lereng, Jarak Jalan, Jarak Sungai, atau Faktor Ekonomi.\n"
            "Metadata setiap faktor akan otomatis diperiksa dan dibandingkan terhadap Peta LULC T1 di sini."
        )
        layout.addWidget(self.driver_audit_box, stretch=2)

        self.tabs.addTab(self.tab_drivers, "3. Variabel Pendorong")

    def _build_tab_log(self):
        self.tab_log = QWidget()
        layout = QVBoxLayout(self.tab_log)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        top_bar = QHBoxLayout()
        info_lbl = QLabel("Analisis Perubahan Luas Tutupan Lahan (Hektar, km², %) & Log Konversi:")
        info_lbl.setStyleSheet("font-weight: bold; color: #334155;")
        top_bar.addWidget(info_lbl)
        top_bar.addStretch()

        btn_export_csv = QPushButton("Export Tabel Luas (.CSV / Excel)")
        btn_export_csv.setObjectName("SoftBlueBtn")
        btn_export_csv.clicked.connect(self._export_area_table_to_csv)
        top_bar.addWidget(btn_export_csv)
        layout.addLayout(top_bar)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFont(QFont("Consolas", 9))
        self.log_box.setPlainText(
            "Tabel perhitungan luas tutupan lahan (LULC) otomatis tampil di sini setelah Anda klik "
            "'1. Cek & Audit Metadata' atau '2. Konversi Semua ke .RST + .RDC'."
        )
        layout.addWidget(self.log_box)
        self.tabs.addTab(self.tab_log, "4. Analisis Luas && Log")

    # ==========================================================================
    # 2. HANDLER INPUT FILE & PENGATURAN SISTEM KOORDINAT (CRS)
    # ==========================================================================

    def _browse_t1(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih File GeoTIFF LULC Tahun Awal (T1)", "", "GeoTIFF Raster (*.tif *.tiff);;All Files (*.*)"
        )
        if path:
            self.t1_edit.setText(path)
            stem = Path(path).stem
            self.t1_outname_edit.setText(f"{stem}_terrset")
            self.t1_title_edit.setText(stem.replace("_", " "))

    def _browse_t2(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih File GeoTIFF LULC Tahun Akhir (T2)", "", "GeoTIFF Raster (*.tif *.tiff);;All Files (*.*)"
        )
        if path:
            self.t2_edit.setText(path)
            stem = Path(path).stem
            self.t2_outname_edit.setText(f"{stem}_terrset")
            self.t2_title_edit.setText(stem.replace("_", " "))

    def _browse_t3(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih File GeoTIFF LULC Tahun ke-3 (T3 Aktual/Validasi)", "", "GeoTIFF Raster (*.tif *.tiff);;All Files (*.*)"
        )
        if path:
            self.t3_edit.setText(path)
            self.use_t3_chk.setChecked(True)
            stem = Path(path).stem
            self.t3_outname_edit.setText(f"{stem}_terrset")
            self.t3_title_edit.setText(stem.replace("_", " "))

    def _on_t3_toggled(self, checked: bool):
        self.t3_outname_edit.setEnabled(checked)
        self.t3_title_edit.setEnabled(checked)

    def _browse_outdir(self):
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder Penyimpanan Output (.rst / .rdc)")
        if folder:
            self.out_dir_edit.setText(folder)

    def _get_selected_target_crs(self) -> str:
        raw_text = self.target_crs_combo.currentText().strip()
        if "—" in raw_text:
            return raw_text.split("—")[0].strip()
        if " - " in raw_text and raw_text.upper().startswith("EPSG:"):
            return raw_text.split(" - ")[0].strip()
        return raw_text

    def _set_target_crs_ui(self, epsg_str: str, ref_sys: str, ref_unit: str):
        self.target_crs_combo.blockSignals(True)
        matched_idx = -1
        for i in range(self.target_crs_combo.count()):
            if self.target_crs_combo.itemData(i) == epsg_str.upper():
                matched_idx = i
                break
        if matched_idx >= 0:
            self.target_crs_combo.setCurrentIndex(matched_idx)
        else:
            self.target_crs_combo.setEditText(epsg_str)
        self.target_crs_combo.blockSignals(False)

        self.ref_sys_edit.setText(ref_sys)
        idx = self.ref_unit_combo.findText(ref_unit)
        if idx >= 0:
            self.ref_unit_combo.setCurrentIndex(idx)

    def _on_crs_preset_changed(self, _index: int):
        epsg_text = self._get_selected_target_crs()
        try:
            _, is_proj, _, ref_sys, ref_unit = parse_crs_info(epsg_text)
            self.ref_sys_edit.setText(ref_sys)
            idx = self.ref_unit_combo.findText(ref_unit)
            if idx >= 0:
                self.ref_unit_combo.setCurrentIndex(idx)
            if is_proj:
                try:
                    cur_res = float(self.target_res_edit.text().strip())
                    if 0 < cur_res < 0.1 and self.meta_t1 is not None:
                        _, _, _, suggested_res_m = suggest_utm_from_metadata(self.meta_t1)
                        self.target_res_edit.setText(f"{suggested_res_m:g}")
                except ValueError:
                    pass
        except Exception:
            pass

    def _auto_detect_utm_from_raster(self):
        if self.meta_t1 is None:
            t1_path = self.t1_edit.text().strip()
            if t1_path and Path(t1_path).is_file():
                self.meta_t1 = inspect_raster_metadata(t1_path)
            else:
                QMessageBox.warning(self, "Pilih File T1 Dulu", "Silakan pilih file GeoTIFF (.tif) T1 terlebih dahulu.")
                return

        epsg_str, ref_sys, ref_unit, res_m = suggest_utm_from_metadata(self.meta_t1)
        self._set_target_crs_ui(epsg_str, ref_sys, ref_unit)
        self.target_res_edit.setText(f"{res_m:g}")
        QMessageBox.information(
            self,
            "Zona UTM Berhasil Dideteksi",
            f"Berdasarkan titik tengah koordinat peta Anda:\n\n"
            f"• Target CRS          : {epsg_str}\n"
            f"• TerrSet ref. system : {ref_sys} ({ref_unit})\n"
            f"• Resolusi Spasial    : {res_m:g} meter",
        )

    def _sync_ref_system_from_epsg(self):
        epsg_text = self._get_selected_target_crs()
        try:
            _, is_proj, _, ref_sys, ref_unit = parse_crs_info(epsg_text)
            self.ref_sys_edit.setText(ref_sys)
            idx = self.ref_unit_combo.findText(ref_unit)
            if idx >= 0:
                self.ref_unit_combo.setCurrentIndex(idx)
            if is_proj:
                try:
                    cur_res = float(self.target_res_edit.text().strip())
                    if 0 < cur_res < 0.1 and self.meta_t1 is not None:
                        _, _, _, suggested_res_m = suggest_utm_from_metadata(self.meta_t1)
                        self.target_res_edit.setText(f"{suggested_res_m:g}")
                except ValueError:
                    pass
            if not is_proj:
                QMessageBox.warning(
                    self,
                    "Peringatan Proyeksi",
                    f"CRS '{epsg_text}' masih bersifat Geografis (derajat).\n"
                    "Gunakan proyeksi UTM (meter) dari daftar dropdown atau klik 'Auto-Deteksi UTM dari Peta'.",
                )
        except Exception as exc:
            QMessageBox.critical(self, "CRS Tidak Valid", f"Gagal mengenali CRS '{epsg_text}':\n{exc}")

    # ==========================================================================
    # 3. HANDLER TAB 3: VARIABEL PENDORONG (DRIVER VARIABLES)
    # ==========================================================================

    def _add_driver_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Pilih File GeoTIFF Variabel Pendorong (DEM, Lereng, Jarak, dll.)",
            "",
            "GeoTIFF Raster (*.tif *.tiff);;All Files (*.*)",
        )
        for p in paths:
            self._append_driver_row(p)
        if paths:
            self.run_driver_metadata_audit()

    def _append_driver_row(self, tif_path: str):
        try:
            meta = inspect_raster_metadata(tif_path)
        except Exception as exc:
            QMessageBox.warning(self, "Gagal Membaca File", f"Tidak dapat membaca {tif_path}:\n{exc}")
            return

        self.driver_metas.append(meta)
        row_idx = self.table_drivers.rowCount()
        self.table_drivers.insertRow(row_idx)

        item_name = QTableWidgetItem(meta["name"])
        item_name.setData(Qt.UserRole, meta["path"])
        item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
        self.table_drivers.setItem(row_idx, 0, item_name)

        crs_dim_str = f"{meta['crs_display']} | {meta['width']}x{meta['height']}"
        item_crs = QTableWidgetItem(crs_dim_str)
        item_crs.setFlags(item_crs.flags() & ~Qt.ItemIsEditable)
        self.table_drivers.setItem(row_idx, 1, item_crs)

        nd_str = f"{meta['nodata']:.3g}" if isinstance(meta["nodata"], float) else str(meta["nodata"])
        range_str = f"{meta['min_val']:.4g} .. {meta['max_val']:.4g} (ND:{nd_str})"
        item_rng = QTableWidgetItem(range_str)
        item_rng.setFlags(item_rng.flags() & ~Qt.ItemIsEditable)
        self.table_drivers.setItem(row_idx, 2, item_rng)

        status_short, _ = audit_driver_against_lulc(meta, self.meta_t1)
        item_st = QTableWidgetItem(status_short)
        item_st.setFlags(item_st.flags() & ~Qt.ItemIsEditable)
        if status_short.startswith("OK") or status_short.startswith("Geometri Cocok"):
            item_st.setBackground(QColor("#ECFDF5"))
            item_st.setForeground(QColor("#065F46"))
        else:
            item_st.setBackground(QColor("#FFFBEB"))
            item_st.setForeground(QColor("#92400E"))
        self.table_drivers.setItem(row_idx, 3, item_st)

        resamp_combo = QComboBox()
        resamp_combo.addItems([
            "Bilinear (Kontinu)",
            "Cubic (Kontinu Halus)",
            "Nearest Neighbor (Kategorikal)",
        ])
        self.table_drivers.setCellWidget(row_idx, 4, resamp_combo)

        dt_combo = QComboBox()
        dt_combo.addItems(["real", "integer", "byte"])
        self.table_drivers.setCellWidget(row_idx, 5, dt_combo)

        stem_lower = Path(tif_path).stem.lower()
        if np.isclose(meta["min_val"], 0.0, atol=0.05) and np.isclose(meta["max_val"], 1.0, atol=0.05):
            default_unit = "index"
        elif "slope" in stem_lower or "lereng" in stem_lower:
            default_unit = "degrees"
        else:
            default_unit = "meters"
        self.table_drivers.setItem(row_idx, 6, QTableWidgetItem(default_unit))

        stem = Path(tif_path).stem
        self.table_drivers.setItem(row_idx, 7, QTableWidgetItem(f"{stem}_TerrSet"))
        self.table_drivers.setItem(row_idx, 8, QTableWidgetItem(stem.replace("_", " ")))

    def run_driver_metadata_audit(self):
        if self.meta_t1 is None:
            t1_path = self.t1_edit.text().strip()
            if t1_path and Path(t1_path).is_file():
                try:
                    self.meta_t1 = inspect_raster_metadata(t1_path)
                except Exception:
                    pass

        row_count = self.table_drivers.rowCount()
        if row_count == 0:
            self.driver_audit_box.setPlainText("Belum ada file Variabel Pendorong yang ditambahkan.")
            return

        report_lines = ["AUDIT METADATA VARIABEL PENDORONG TERHADAP LULC T1:"]
        if self.meta_t1 is not None:
            report_lines.append(
                f"Acuan LULC T1: {self.meta_t1['name']} | CRS: {self.meta_t1['crs_display']} | "
                f"Dimensi: {self.meta_t1['width']}x{self.meta_t1['height']} | "
                f"Resolusi: {self.meta_t1['res_x']:.5g}x{self.meta_t1['res_y']:.5g}"
            )
        report_lines.append("=" * 96)

        for r_idx in range(row_count):
            drv_path = self.table_drivers.item(r_idx, 0).data(Qt.UserRole)
            meta = inspect_raster_metadata(drv_path)
            if r_idx < len(self.driver_metas):
                self.driver_metas[r_idx] = meta

            status_short, detail_lines = audit_driver_against_lulc(meta, self.meta_t1)
            item_st = QTableWidgetItem(status_short)
            item_st.setFlags(item_st.flags() & ~Qt.ItemIsEditable)
            if status_short.startswith("OK") or status_short.startswith("Geometri Cocok"):
                item_st.setBackground(QColor("#ECFDF5"))
                item_st.setForeground(QColor("#065F46"))
            else:
                item_st.setBackground(QColor("#FFFBEB"))
                item_st.setForeground(QColor("#92400E"))
            self.table_drivers.setItem(r_idx, 3, item_st)

            report_lines.extend(detail_lines)
            report_lines.append("-" * 96)

        self.driver_audit_box.setPlainText("\n".join(report_lines))

    def _remove_selected_driver(self):
        cur_row = self.table_drivers.currentRow()
        if cur_row >= 0:
            self.table_drivers.removeRow(cur_row)
            if cur_row < len(self.driver_metas):
                self.driver_metas.pop(cur_row)
            self.run_driver_metadata_audit()

    def _clear_all_drivers(self):
        self.table_drivers.setRowCount(0)
        self.driver_metas.clear()
        self.run_driver_metadata_audit()

    # ==========================================================================
    # 4. DATA SAMPEL & TABEL LEGENDA
    # ==========================================================================

    def _generate_sample_data(self):
        try:
            sample_dir = self.base_dir / "sample_lulc_tif"
            t1_path, t2_path, t3_path, driver_paths = create_sample_lulc_tifs(sample_dir)

            self.t1_edit.setText(str(t1_path))
            self.t2_edit.setText(str(t2_path))
            self.t3_edit.setText(str(t3_path))
            self.use_t3_chk.setChecked(True)

            self.t1_outname_edit.setText("LULC_2015_TerrSet")
            self.t2_outname_edit.setText("LULC_2020_TerrSet")
            self.t3_outname_edit.setText("LULC_2025_Aktual_TerrSet")
            self.t1_title_edit.setText("Tutupan Lahan 2015")
            self.t2_title_edit.setText("Tutupan Lahan 2020")
            self.t3_title_edit.setText("Tutupan Lahan 2025 Aktual")

            self.table_drivers.setRowCount(0)
            self.driver_metas.clear()
            for dp in driver_paths:
                self._append_driver_row(str(dp))

            self.run_metadata_check()
            QMessageBox.information(
                self,
                "Data Sampel Siap",
                f"5 file sampel GeoTIFF (LULC 2015, 2020, 2025 + DEM & Jarak Jalan) telah dimuat dari:\n{sample_dir}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Gagal Membuat Data Sampel", str(exc))

    def _populate_legend_table(self, meta1: Dict, meta2: Dict, meta3: Optional[Dict]):
        codes_set = set(meta1["class_counts"].keys()) | set(meta2["class_counts"].keys())
        if meta3 is not None:
            codes_set |= set(meta3["class_counts"].keys())
        all_codes = sorted(codes_set)

        self.table_legend.setRowCount(len(all_codes))

        for row_idx, code_val in enumerate(all_codes):
            cnt1 = meta1["class_counts"].get(code_val, 0)
            cnt2 = meta2["class_counts"].get(code_val, 0)
            cnt3_str = f"{meta3['class_counts'].get(code_val, 0):,}" if meta3 is not None else "—"

            item_old = QTableWidgetItem(str(code_val))
            item_old.setFlags(item_old.flags() & ~Qt.ItemIsEditable)
            self.table_legend.setItem(row_idx, 0, item_old)

            item_c1 = QTableWidgetItem(f"{cnt1:,}")
            item_c1.setFlags(item_c1.flags() & ~Qt.ItemIsEditable)
            self.table_legend.setItem(row_idx, 1, item_c1)

            item_c2 = QTableWidgetItem(f"{cnt2:,}")
            item_c2.setFlags(item_c2.flags() & ~Qt.ItemIsEditable)
            self.table_legend.setItem(row_idx, 2, item_c2)

            item_c3 = QTableWidgetItem(cnt3_str)
            item_c3.setFlags(item_c3.flags() & ~Qt.ItemIsEditable)
            self.table_legend.setItem(row_idx, 3, item_c3)

            item_new = QTableWidgetItem(str(code_val))
            self.table_legend.setItem(row_idx, 4, item_new)

            default_lbl = (
                "Background / NoData"
                if code_val == 0
                else DEFAULT_CLASS_NAMES.get(code_val, f"Kelas Tutupan Lahan {code_val}")
            )
            item_lbl = QTableWidgetItem(default_lbl)
            self.table_legend.setItem(row_idx, 5, item_lbl)

    def _auto_shift_codes_from_one(self):
        row_count = self.table_legend.rowCount()
        for row_idx in range(row_count):
            new_code = row_idx + 1
            self.table_legend.item(row_idx, 4).setText(str(new_code))
            cur_lbl = self.table_legend.item(row_idx, 5).text().strip()
            if cur_lbl == "Background / NoData":
                self.table_legend.item(row_idx, 5).setText(
                    DEFAULT_CLASS_NAMES.get(new_code, f"Kelas Tutupan Lahan {new_code}")
                )

    def _reset_class_codes(self):
        row_count = self.table_legend.rowCount()
        for row_idx in range(row_count):
            old_code_str = self.table_legend.item(row_idx, 0).text()
            self.table_legend.item(row_idx, 4).setText(old_code_str)

    # ==========================================================================
    # 5. TAHAP 1: CEK & AUDIT METADATA + HITUNG LUAS OTOMATIS
    # ==========================================================================

    def run_metadata_check(self):
        t1_path = self.t1_edit.text().strip()
        t2_path = self.t2_edit.text().strip()
        t3_path = self.t3_edit.text().strip()

        if not t1_path or not Path(t1_path).is_file():
            QMessageBox.warning(self, "File T1 Belum Valid", "Pilih file GeoTIFF (.tif) Tahun Awal (T1) terlebih dahulu.")
            return
        if not t2_path or not Path(t2_path).is_file():
            QMessageBox.warning(self, "File T2 Belum Valid", "Pilih file GeoTIFF (.tif) Tahun Akhir (T2) terlebih dahulu.")
            return

        use_t3 = self.use_t3_chk.isChecked() and bool(t3_path)
        if self.use_t3_chk.isChecked() and (not t3_path or not Path(t3_path).is_file()):
            QMessageBox.warning(
                self,
                "File T3 Belum Valid",
                "Checkbox LULC T3 aktif tetapi file belum dipilih. Pilih file T3 atau matikan centang T3.",
            )
            return

        try:
            self.meta_t1 = inspect_raster_metadata(t1_path)
            self.meta_t2 = inspect_raster_metadata(t2_path)
            self.meta_t3 = inspect_raster_metadata(t3_path) if use_t3 else None
        except Exception as exc:
            QMessageBox.critical(self, "Gagal Membaca GeoTIFF", f"Kesalahan saat membaca file .tif:\n{exc}")
            return

        rows = compare_lulc_metadata_for_lcm(self.meta_t1, self.meta_t2, self.meta_t3)
        self.table_audit.setRowCount(len(rows))
        issues = []

        for r_idx, (param, v1, v2, v3, status) in enumerate(rows):
            self.table_audit.setItem(r_idx, 0, QTableWidgetItem(param))
            self.table_audit.setItem(r_idx, 1, QTableWidgetItem(v1))
            self.table_audit.setItem(r_idx, 2, QTableWidgetItem(v2))
            self.table_audit.setItem(r_idx, 3, QTableWidgetItem(v3))

            status_item = QTableWidgetItem(status)
            if status.startswith("OK"):
                status_item.setBackground(QColor("#ECFDF5"))
                status_item.setForeground(QColor("#065F46"))
            else:
                status_item.setBackground(QColor("#FFFBEB"))
                status_item.setForeground(QColor("#92400E"))
                issues.append(f"  • {param}: {status}")
            self.table_audit.setItem(r_idx, 4, status_item)

        epsg_utm, ref_sys_utm, ref_unit_utm, res_m = suggest_utm_from_metadata(self.meta_t1)
        self._set_target_crs_ui(epsg_utm, ref_sys_utm, ref_unit_utm)
        self.target_res_edit.setText(f"{res_m:g}")

        self._populate_legend_table(self.meta_t1, self.meta_t2, self.meta_t3)
        self.run_driver_metadata_audit()

        summary_lines = [
            f"LULC T1 : {self.meta_t1['name']} ({self.meta_t1['crs_display']})",
            f"LULC T2 : {self.meta_t2['name']} ({self.meta_t2['crs_display']})",
            f"LULC T3 : {self.meta_t3['name'] + ' (' + self.meta_t3['crs_display'] + ')' if self.meta_t3 else 'Tidak digunakan'}",
            f"Faktor  : {self.table_drivers.rowCount()} file terdaftar di Tab 3",
            "-" * 92,
        ]
        if not self.meta_t1["is_projected"]:
            summary_lines.append(
                f"[Auto-UTM] Data asli masih Geografis ({self.meta_t1['crs_display']}). "
                f"Target CRS di Tab 2 otomatis disetel ke {epsg_utm} ({ref_sys_utm}, resolusi {res_m:g} m)."
            )

        if not issues:
            summary_lines.append("Status: Seluruh parameter geometri LULC sudah identik dan siap dikonversi ke .RST + .RDC.")
        else:
            summary_lines.append(f"Ditemukan {len(issues)} parameter yang akan diselaraskan otomatis saat konversi:")
            summary_lines.extend(issues)

        self.audit_summary_box.setPlainText("\n".join(summary_lines))
        self.run_quick_area_calculation(switch_tab=False)
        self.tabs.setCurrentWidget(self.tab_audit)

    def run_quick_area_calculation(self, switch_tab: bool = True):
        if self.meta_t1 is None or self.meta_t2 is None:
            return

        try:
            target_crs_input = self._get_selected_target_crs()
            _, is_proj, _, ref_sys, ref_unit = parse_crs_info(target_crs_input)
            target_res = float(self.target_res_edit.text().strip())
            if is_proj and target_res < 0.1:
                _, _, _, target_res = suggest_utm_from_metadata(self.meta_t1)
                self.target_res_edit.setText(f"{target_res:g}")

            flag_val = int(self.flag_val_edit.text().strip())
            extent_mode = self.extent_mode_combo.currentText().strip()

            reclass_map: Dict[int, int] = {}
            legend_classes: Dict[int, str] = {}
            for r_idx in range(self.table_legend.rowCount()):
                old_code = int(self.table_legend.item(r_idx, 0).text().strip())
                new_code = int(self.table_legend.item(r_idx, 4).text().strip())
                label_str = self.table_legend.item(r_idx, 5).text().strip() or f"Kelas {new_code}"
                reclass_map[old_code] = new_code
                if new_code != flag_val:
                    legend_classes[new_code] = label_str

            target_wkt, _, _, min_x, min_y, max_x, max_y, cols, rows = compute_unified_grid(
                self.meta_t1, self.meta_t2, target_crs_input, target_res, extent_mode, self.meta_t3
            )

            arr_t1 = align_and_reclass_raster(
                self.meta_t1["path"], self.meta_t1["crs_wkt"] or target_wkt, target_wkt,
                min_x, min_y, max_x, max_y, cols, rows, target_res, flag_val, reclass_map,
            )
            arr_t2 = align_and_reclass_raster(
                self.meta_t2["path"], self.meta_t2["crs_wkt"] or target_wkt, target_wkt,
                min_x, min_y, max_x, max_y, cols, rows, target_res, flag_val, reclass_map,
            )

            arr_t3 = None
            if self.meta_t3 is not None and self.use_t3_chk.isChecked():
                arr_t3 = align_and_reclass_raster(
                    self.meta_t3["path"], self.meta_t3["crs_wkt"] or target_wkt, target_wkt,
                    min_x, min_y, max_x, max_y, cols, rows, target_res, flag_val, reclass_map,
                )

            common_bg = (arr_t1 == flag_val) | (arr_t2 == flag_val)
            if arr_t3 is not None:
                common_bg = common_bg | (arr_t3 == flag_val)

            arr_t1[common_bg] = flag_val
            arr_t2[common_bg] = flag_val
            if arr_t3 is not None:
                arr_t3[common_bg] = flag_val

            pixel_area_m2 = (target_res * target_res) if ref_unit == "m" else 0.0
            pixel_area_ha = pixel_area_m2 / 10000.0
            pixel_area_km2 = pixel_area_m2 / 1000000.0
            total_valid_px = int(np.sum(arr_t1 != flag_val))
            total_area_ha = total_valid_px * pixel_area_ha
            total_area_km2 = total_valid_px * pixel_area_km2

            lines = [
                "=" * 106,
                "HASIL PERHITUNGAN LUAS & PERUBAHAN TUTUPAN LAHAN (SANITY CHECK SPASIAL)",
                "=" * 106,
                f"  • Peta T1 (Awal)           : {self.meta_t1['name']}",
                f"  • Peta T2 (Akhir)          : {self.meta_t2['name']}",
            ]
            if arr_t3 is not None and self.meta_t3 is not None:
                lines.append(f"  • Peta T3 (Aktual/Validasi): {self.meta_t3['name']}")

            lines.extend([
                f"  • Sistem Proyeksi (CRS)    : {target_crs_input} (TerrSet ref. system: '{ref_sys}', satuan: '{ref_unit}')",
                f"  • Dimensi & Resolusi Grid  : {cols} kolom x {rows} baris | Resolusi = {target_res:g} {ref_unit} "
                f"(1 piksel = {pixel_area_m2:,.2f} m² = {pixel_area_ha:.4f} ha)",
                f"  • Total Luas Wilayah Studi : {total_area_ha:,.2f} ha  |  {total_area_km2:,.4f} km²  ({total_valid_px:,} piksel valid)",
                "-" * 106,
            ])

            self.last_area_csv_rows = []

            if arr_t3 is not None:
                lines.append(
                    f"{'Kode':<5} {'Nama Kelas Tutupan Lahan':<26} {'Luas T1 (ha)':>13} {'Luas T2 (ha)':>13} {'Luas T3 (ha)':>13} {'T1->T2 (ha)':>13} {'T2->T3 (ha)':>13} {'T2 (%)':>8}"
                )
                lines.append("-" * 106)
                self.last_area_csv_rows.append([
                    "Kode", "Nama_Kelas", "Piksel_T1", "Luas_T1_ha", "Luas_T1_km2", "Persen_T1",
                    "Piksel_T2", "Luas_T2_ha", "Luas_T2_km2", "Persen_T2",
                    "Piksel_T3", "Luas_T3_ha", "Luas_T3_km2", "Persen_T3",
                    "Perubahan_T1_T2_ha", "Perubahan_T2_T3_ha",
                ])
                for code_num in sorted(legend_classes.keys()):
                    name = legend_classes[code_num]
                    px1 = int(np.sum(arr_t1 == code_num))
                    px2 = int(np.sum(arr_t2 == code_num))
                    px3 = int(np.sum(arr_t3 == code_num))
                    ha1, ha2, ha3 = px1 * pixel_area_ha, px2 * pixel_area_ha, px3 * pixel_area_ha
                    pct1 = (ha1 / total_area_ha * 100.0) if total_area_ha > 0 else 0.0
                    pct2 = (ha2 / total_area_ha * 100.0) if total_area_ha > 0 else 0.0
                    pct3 = (ha3 / total_area_ha * 100.0) if total_area_ha > 0 else 0.0
                    lines.append(
                        f"{code_num:<5} {name[:25]:<26} {ha1:>13,.2f} {ha2:>13,.2f} {ha3:>13,.2f} {ha2 - ha1:>+13,.2f} {ha3 - ha2:>+13,.2f} {pct2:>7.2f}%"
                    )
                    self.last_area_csv_rows.append([
                        code_num, name, px1, round(ha1, 4), round(ha1 / 100.0, 6), round(pct1, 2),
                        px2, round(ha2, 4), round(ha2 / 100.0, 6), round(pct2, 2),
                        px3, round(ha3, 4), round(ha3 / 100.0, 6), round(pct3, 2),
                        round(ha2 - ha1, 4), round(ha3 - ha2, 4),
                    ])
                lines.append("-" * 106)
                lines.append(
                    f"{'TOTAL':<5} {'Luas Valid Wilayah Studi':<26} {total_area_ha:>13,.2f} {total_area_ha:>13,.2f} {total_area_ha:>13,.2f} {0.0:>+13,.2f} {0.0:>+13,.2f} {'100.00%':>8}"
                )
            else:
                lines.append(
                    f"{'Kode':<5} {'Nama Kelas Tutupan Lahan':<28} {'Luas T1 (ha)':>14} {'T1 (%)':>8} {'Luas T2 (ha)':>14} {'T2 (%)':>8} {'Perubahan (ha)':>15} {'Perubahan (km²)':>15}"
                )
                lines.append("-" * 106)
                self.last_area_csv_rows.append([
                    "Kode", "Nama_Kelas", "Piksel_T1", "Luas_T1_ha", "Luas_T1_km2", "Proporsi_T1_Persen",
                    "Piksel_T2", "Luas_T2_ha", "Luas_T2_km2", "Proporsi_T2_Persen",
                    "Perubahan_ha", "Perubahan_km2", "Laju_Perubahan_Kelas_Persen",
                ])
                for code_num in sorted(legend_classes.keys()):
                    name = legend_classes[code_num]
                    px1 = int(np.sum(arr_t1 == code_num))
                    px2 = int(np.sum(arr_t2 == code_num))
                    ha1, ha2 = px1 * pixel_area_ha, px2 * pixel_area_ha
                    km1, km2 = px1 * pixel_area_km2, px2 * pixel_area_km2
                    pct1 = (ha1 / total_area_ha * 100.0) if total_area_ha > 0 else 0.0
                    pct2 = (ha2 / total_area_ha * 100.0) if total_area_ha > 0 else 0.0
                    diff_ha = ha2 - ha1
                    diff_km2 = km2 - km1
                    rate_pct = ((ha2 - ha1) / ha1 * 100.0) if ha1 > 0 else 0.0
                    lines.append(
                        f"{code_num:<5} {name[:27]:<28} {ha1:>14,.2f} {pct1:>7.2f}% {ha2:>14,.2f} {pct2:>7.2f}% {diff_ha:>+15,.2f} {diff_km2:>+15,.4f}"
                    )
                    self.last_area_csv_rows.append([
                        code_num, name, px1, round(ha1, 4), round(km1, 6), round(pct1, 2),
                        px2, round(ha2, 4), round(km2, 6), round(pct2, 2),
                        round(diff_ha, 4), round(diff_km2, 6), round(rate_pct, 2),
                    ])
                lines.append("-" * 106)
                lines.append(
                    f"{'TOTAL':<5} {'Luas Valid Wilayah Studi':<28} {total_area_ha:>14,.2f} {'100.00%':>8} {total_area_ha:>14,.2f} {'100.00%':>8} {0.0:>+15,.2f} {0.0:>+15,.4f}"
                )

            lines.append("=" * 106)
            self.log_box.setPlainText("\n".join(lines))
            if switch_tab:
                self.tabs.setCurrentWidget(self.tab_log)

        except Exception as exc:
            if switch_tab:
                QMessageBox.critical(self, "Gagal Menghitung Luas", str(exc))

    def _export_area_table_to_csv(self):
        if not self.last_area_csv_rows:
            self.run_quick_area_calculation(switch_tab=True)
            if not self.last_area_csv_rows:
                return

        default_csv = str(Path(self.out_dir_edit.text().strip()) / "Tabel_Perubahan_Luas_LULC.csv")
        csv_path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Tabel Perubahan Luas LULC ke CSV", default_csv, "CSV Files (*.csv);;All Files (*.*)"
        )
        if not csv_path:
            return

        Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f_csv:
            writer = csv.writer(f_csv)
            writer.writerows(self.last_area_csv_rows)

        QMessageBox.information(
            self,
            "CSV Berhasil Disimpan",
            f"Tabel perhitungan luas telah disimpan ke:\n{csv_path}",
        )

    # ==========================================================================
    # 6. TAHAP 2: PENYELARASAN SPASIAL & KONVERSI SEMUA KE .RST + .RDC
    # ==========================================================================

    def run_alignment_and_export(self):
        if self.meta_t1 is None or self.meta_t2 is None:
            self.run_metadata_check()
            if self.meta_t1 is None or self.meta_t2 is None:
                return

        try:
            target_crs_input = self._get_selected_target_crs()
            _, is_proj, _, _, _ = parse_crs_info(target_crs_input)
            target_res = float(self.target_res_edit.text().strip())
            if target_res <= 0:
                raise ValueError("Resolusi spasial harus lebih besar dari 0.")

            if is_proj and target_res < 0.1:
                _, _, _, est_res_m = suggest_utm_from_metadata(self.meta_t1)
                ans = QMessageBox.question(
                    self,
                    "Resolusi Masih Dalam Derajat",
                    f"Target CRS Anda dalam meter ({target_crs_input}), tetapi resolusi tertulis {target_res}.\n"
                    f"Ubah resolusi menjadi {est_res_m:g} meter?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if ans == QMessageBox.Yes:
                    target_res = est_res_m
                    self.target_res_edit.setText(f"{target_res:g}")

            if not is_proj:
                ans = QMessageBox.question(
                    self,
                    "Konfirmasi CRS Geografis",
                    "Target CRS masih dalam derajat (Geografis). Tetap lanjutkan?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if ans != QMessageBox.Yes:
                    return

            data_type_terrset = self.dtype_combo.currentText().strip()
            flag_val = int(self.flag_val_edit.text().strip())
            ref_sys = self.ref_sys_edit.text().strip()
            ref_unit = self.ref_unit_combo.currentText().strip()
            extent_mode = self.extent_mode_combo.currentText().strip()

            reclass_map: Dict[int, int] = {}
            legend_classes: Dict[int, str] = {}
            for r_idx in range(self.table_legend.rowCount()):
                old_code = int(self.table_legend.item(r_idx, 0).text().strip())
                new_code = int(self.table_legend.item(r_idx, 4).text().strip())
                label_str = self.table_legend.item(r_idx, 5).text().strip() or f"Kelas {new_code}"
                reclass_map[old_code] = new_code
                if new_code != flag_val:
                    legend_classes[new_code] = label_str

            if not legend_classes:
                raise ValueError("Tidak ada kelas tutupan lahan aktif (selain Background/NoData)!")

            target_wkt, _, _, min_x, min_y, max_x, max_y, cols, rows = compute_unified_grid(
                self.meta_t1, self.meta_t2, target_crs_input, target_res, extent_mode, self.meta_t3
            )

            arr_t1 = align_and_reclass_raster(
                self.meta_t1["path"], self.meta_t1["crs_wkt"] or target_wkt, target_wkt,
                min_x, min_y, max_x, max_y, cols, rows, target_res, flag_val, reclass_map,
            )
            arr_t2 = align_and_reclass_raster(
                self.meta_t2["path"], self.meta_t2["crs_wkt"] or target_wkt, target_wkt,
                min_x, min_y, max_x, max_y, cols, rows, target_res, flag_val, reclass_map,
            )

            arr_t3 = None
            if self.meta_t3 is not None and self.use_t3_chk.isChecked():
                arr_t3 = align_and_reclass_raster(
                    self.meta_t3["path"], self.meta_t3["crs_wkt"] or target_wkt, target_wkt,
                    min_x, min_y, max_x, max_y, cols, rows, target_res, flag_val, reclass_map,
                )

            common_bg = (arr_t1 == flag_val) | (arr_t2 == flag_val)
            if arr_t3 is not None:
                common_bg = common_bg | (arr_t3 == flag_val)

            arr_t1[common_bg] = flag_val
            arr_t2[common_bg] = flag_val
            if arr_t3 is not None:
                arr_t3[common_bg] = flag_val

            out_dir = Path(self.out_dir_edit.text().strip())
            out_dir.mkdir(parents=True, exist_ok=True)

            min_code = float(min(legend_classes.keys()))
            max_code = float(max(legend_classes.keys()))

            t1_base = out_dir / self.t1_outname_edit.text().strip()
            rst1, rdc1 = write_idrisi_rst_rdc(
                output_base_path=t1_base, array_2d=arr_t1,
                title=self.t1_title_edit.text().strip(), data_type_terrset=data_type_terrset,
                ref_system=ref_sys, ref_units=ref_unit, min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y,
                resolution=target_res, flag_value=float(flag_val), flag_defn="background",
                value_units="classes", legend_classes=legend_classes,
                forced_min_val=min_code, forced_max_val=max_code,
            )

            t2_base = out_dir / self.t2_outname_edit.text().strip()
            rst2, rdc2 = write_idrisi_rst_rdc(
                output_base_path=t2_base, array_2d=arr_t2,
                title=self.t2_title_edit.text().strip(), data_type_terrset=data_type_terrset,
                ref_system=ref_sys, ref_units=ref_unit, min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y,
                resolution=target_res, flag_value=float(flag_val), flag_defn="background",
                value_units="classes", legend_classes=legend_classes,
                forced_min_val=min_code, forced_max_val=max_code,
            )

            rst3, rdc3 = None, None
            if arr_t3 is not None:
                t3_base = out_dir / self.t3_outname_edit.text().strip()
                rst3, rdc3 = write_idrisi_rst_rdc(
                    output_base_path=t3_base, array_2d=arr_t3,
                    title=self.t3_title_edit.text().strip(), data_type_terrset=data_type_terrset,
                    ref_system=ref_sys, ref_units=ref_unit, min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y,
                    resolution=target_res, flag_value=float(flag_val), flag_defn="background",
                    value_units="classes", legend_classes=legend_classes,
                    forced_min_val=min_code, forced_max_val=max_code,
                )

            if self.save_tif_chk.isChecked():
                save_geotiff(
                    t1_base.with_name(t1_base.name + "_aligned.tif"),
                    arr_t1, target_wkt, min_x, min_y, max_x, max_y, target_res, data_type_terrset, flag_val
                )
                save_geotiff(
                    t2_base.with_name(t2_base.name + "_aligned.tif"),
                    arr_t2, target_wkt, min_x, min_y, max_x, max_y, target_res, data_type_terrset, flag_val
                )
                if arr_t3 is not None:
                    t3_base = out_dir / self.t3_outname_edit.text().strip()
                    save_geotiff(
                        t3_base.with_name(t3_base.name + "_aligned.tif"),
                        arr_t3, target_wkt, min_x, min_y, max_x, max_y, target_res, data_type_terrset, flag_val
                    )

            driver_outputs = []
            sync_drv_bg = self.sync_driver_bg_chk.isChecked()
            valid_study_mask = ~common_bg
            for d_idx in range(self.table_drivers.rowCount()):
                drv_path = self.table_drivers.item(d_idx, 0).data(Qt.UserRole)
                resamp_text = self.table_drivers.cellWidget(d_idx, 4).currentText()
                drv_dtype = self.table_drivers.cellWidget(d_idx, 5).currentText()
                drv_units = self.table_drivers.item(d_idx, 6).text().strip() or "meters"
                drv_outname = self.table_drivers.item(d_idx, 7).text().strip() or f"Driver_{d_idx + 1}"
                drv_title = self.table_drivers.item(d_idx, 8).text().strip() or drv_outname

                drv_meta = inspect_raster_metadata(drv_path)
                drv_arr = align_driver_raster(
                    tif_path=drv_path,
                    src_wkt_fallback=drv_meta["crs_wkt"] or target_wkt,
                    target_wkt=target_wkt,
                    min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y,
                    cols=cols, rows=rows, target_res=target_res,
                    resampling_method=resamp_text,
                    flag_val=float(flag_val),
                    common_bg_mask=common_bg if sync_drv_bg else None,
                )

                drv_base = out_dir / drv_outname
                d_rst, d_rdc = write_idrisi_rst_rdc(
                    output_base_path=drv_base,
                    array_2d=drv_arr,
                    title=drv_title,
                    data_type_terrset=drv_dtype,
                    ref_system=ref_sys,
                    ref_units=ref_unit,
                    min_x=min_x, max_x=max_x, min_y=min_y, max_y=max_y,
                    resolution=target_res,
                    flag_value=float(flag_val),
                    flag_defn="background",
                    value_units=drv_units,
                    legend_classes=None,
                    valid_mask_override=valid_study_mask if sync_drv_bg else None,
                )
                if self.save_tif_chk.isChecked():
                    save_geotiff(
                        drv_base.with_name(drv_base.name + "_aligned.tif"),
                        drv_arr, target_wkt, min_x, min_y, max_x, max_y, target_res, drv_dtype, float(flag_val)
                    )
                driver_outputs.append((drv_title, d_rst, d_rdc, resamp_text, drv_dtype))

            self.run_quick_area_calculation(switch_tab=False)
            area_text = self.log_box.toPlainText()

            extra_lines = [
                "",
                "FILE OUTPUT TERRSET (.RST & .RDC) YANG DIHASILKAN:",
                f"  • LULC T1 : {rst1.name} & {rdc1.name}",
                f"  • LULC T2 : {rst2.name} & {rdc2.name}",
            ]
            if rst3 is not None and rdc3 is not None:
                extra_lines.append(f"  • LULC T3 : {rst3.name} & {rdc3.name}")
            for d_title, d_rst, d_rdc, d_resamp, d_dt in driver_outputs:
                extra_lines.append(f"  • Faktor  : {d_rst.name} & {d_rdc.name} ({d_title} | {d_dt} | {d_resamp})")

            extra_lines.extend([
                "",
                "PRATINJAU ISI FILE .RDC (T1):",
                "-" * 106,
                rdc1.read_text(encoding="ascii", errors="replace"),
            ])

            self.log_box.setPlainText(area_text + "\n" + "\n".join(extra_lines))
            self.tabs.setCurrentWidget(self.tab_log)

            msg_lines = [
                "Seluruh data berhasil diselaraskan dan dikonversi ke format TerrSet (.rst + .rdc)!",
                "",
                f"• LULC T1 : {rst1.name}",
                f"• LULC T2 : {rst2.name}",
            ]
            if rst3 is not None:
                msg_lines.append(f"• LULC T3 : {rst3.name}")
            if driver_outputs:
                msg_lines.append(f"• Faktor  : {len(driver_outputs)} pasang file (.rst/.rdc)")
            msg_lines.extend(["", f"Lokasi Output:\n{out_dir}"])

            QMessageBox.information(self, "Konversi Selesai", "\n".join(msg_lines))

        except Exception as exc:
            QMessageBox.critical(self, "Gagal Melakukan Konversi", f"Terjadi kesalahan:\n{exc}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(MODERN_GIS_STYLESHEET)
    win = TerrSetLCMConverterWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
