import openpyxl


def build_di319(path, periode="20/08/2026", date_printed="21/08/2026", extra_rows=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["BANK XYZ"])
    ws.append(["SAVINGS ACCOUNT MONTHLY TRIAL BALANCE"])
    ws.append(["Date Printed:", date_printed])
    ws.append([])
    ws.append([
        "periode", "account number", "ciff no", "short name", "prod code", "curr code",
        "balance", "Balance dalam IDR", "PN RM Dana/Mantri", "PN RM Referral", "PN Customer Service",
    ])
    ws.append([periode, "1234567890", "CIF001", "PT ABC", "SAV", "IDR",
               1_000_000, 1_000_000, "00382271 Ahmad Rafiq", "00274689 - Dia Silopa Putri", None])
    ws.append([periode, "1234567891", "CIF002", "PT DEF", "SAV", "IDR",
               2_000_000, 2_000_000, "00380727 - Adist Ayudistira Sembiring", None, None])
    for extra in (extra_rows or []):
        ws.append(extra)
    ws.append(["", "TOTAL", "", "", "", "", 3000000, 3000000, "", "", ""])
    wb.save(path)


def build_di321(path, periode="20/08/2026"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["CURRENT ACCOUNT MONTHLY TRIAL BALANCE"])
    ws.append(["Date Printed", "21/08/2026"])
    ws.append([])
    ws.append([
        "PERIODE", "CIFNO", "ACCOUNT NUMBER", "PRODUCT CODE", "SHORT NAME", "STATUS",
        "BALANCE", "AVAIL BALANCE", "AVRG BALANCE", "CURR", "PN RM DANA",
    ])
    ws.append([periode, "CIF010", "9988776655", "GIR", "PT SUKSES", "ACTIVE",
               15_000_000, 14_500_000, 14_800_000, "IDR", "00274689 Dia Silopa"])
    wb.save(path)


def build_edc(path, periode="31/08/2026", rows=None):
    """Mirrors the real edc_31_agustus.xlsx column layout: TAHUN, PERIODE,
    POSISI, NAMA_UKER, TID, MID, NAMA_MERCHANT, JENIS, NAMA_USER_PEMRAKARSA,
    ALAMAT_MERCHANT, SALES_VOLUME, NOREK."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([
        "TAHUN", "PERIODE", "POSISI", "NAMA_UKER", "TID", "MID", "NAMA_MERCHANT", "JENIS",
        "NAMA_USER_PEMRAKARSA", "ALAMAT_MERCHANT", "SALES_VOLUME", "NOREK",
    ])
    default_rows = [
        [2026, periode, periode, "KC JAKARTA", "TID001", "MID001", "TOKO MAJU", "EDC",
         "Adist Ayudistira", "Jl. Sudirman", 20_000_000, "1234567890"],
        [2026, periode, periode, "KC JAKARTA", "TID002", "MID002", "TOKO SEDANG", "EDC",
         "ADIST AYUDISTIRA", "Jl. Thamrin", 5_000_000, "1234567891"],
        [2026, periode, periode, "KC JAKARTA", "TID003", "MID003", "TOKO SEPI", "EDC",
         "Dia Silopa", "Jl. Gatot Subroto", 0, "9999999999"],
    ]
    for row in (rows if rows is not None else default_rows):
        ws.append(row)
    wb.save(path)


def build_qris(path, periode="31/08/2026", rows=None):
    """Mirrors the real qris_31_agustus.xlsx column layout: PERIODE, POSISI,
    BRDESC, MERCHANT_PAN, STOREID, NAMA_MERCHANT, ALAMAT, PN_PEMRAKASA,
    STATUS, POSISI_SV_TOTAL, NO_REK."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([
        "PERIODE", "POSISI", "BRDESC", "MERCHANT_PAN", "STOREID", "NAMA_MERCHANT", "ALAMAT",
        "PN_PEMRAKASA", "STATUS", "POSISI_SV_TOTAL", "NO_REK",
    ])
    default_rows = [
        [periode, periode, "KC JAKARTA", "PAN001", "ST001", "WARUNG A", "Jl. Melati",
         "Ahmad Rafiq", "ACTIVE", 80_000, "9988776655"],
        [periode, periode, "KC JAKARTA", "PAN002", "ST002", "WARUNG B", "Jl. Mawar",
         "AHMAD RAFIQ", "ACTIVE", 10_000, "9988776656"],
    ]
    for row in (rows if rows is not None else default_rows):
        ws.append(row)
    wb.save(path)


def build_ci324(path, periode="20/08/2026"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["FDs MONTHLY TRIAL BALANCE"])
    ws.append(["Date Printed :", "21/08/2026"])
    ws.append([])
    ws.append([
        "PERIODE", "ACCTNO", "FDR SRL NO", "SHORT NAME", "TYPE", "PRINCIPAL AMOUNT",
        "ISSUE DT", "MAT DT", "INT RATE", "INT TENOR DISP", "RENEW", "CBAL Base", "PN RM Dana",
    ])
    ws.append([periode, "5566778899", "FDR001", "PT MAKMUR", "FD", 100_000_000,
               "20/02/2026", "20/02/2027", 5.5, "12M", "AUTO", None, "00380727 Adist Ayudistira"])
    wb.save(path)
