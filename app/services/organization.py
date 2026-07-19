"""Master organisasi FEWS dari Wilayah, Area, dan Lokasi.pptx."""

from __future__ import annotations


_MASTER_TEXT = """
Sumatera Bagian Utara|Area Aceh|Jambo Tape
Sumatera Bagian Utara|Area Aceh|Merduati
Sumatera Bagian Utara|Area Medan|Medan Baru
Sumatera Bagian Utara|Area Medan|Medan Helvetia
Sumatera Bagian Utara|Area Medan|Medan Area
Sumatera Bagian Utara|Area Medan|Medan Johor
Sumatera Bagian Utara|Area Pekanbaru|Hangtuah
Sumatera Bagian Utara|Area Pekanbaru|Tanjung Datuk
Sumatera Bagian Utara|Area Pekanbaru|Panam
Sumatera Bagian Utara|Area Sumatra Barat|Payakumbuh
Sumatera Bagian Utara|Area Sumatra Barat|Bukit Tinggi
Sumatera Bagian Selatan|Area Jambi|The Hok
Sumatera Bagian Selatan|Area Jambi|Telanai Jambi
Sumatera Bagian Selatan|Area Palembang|Sudirman
Sumatera Bagian Selatan|Area Palembang|Sukamto
Sumatera Bagian Selatan|Area Palembang|Punti Kayu
Sumatera Bagian Selatan|Area Lampung|Rajabasa
Sumatera Bagian Selatan|Area Lampung|Metro
Sumatera Bagian Selatan|Area Lampung|Way Halim
Sumatera Bagian Selatan|Area Lampung|Pahoman
Sumatera Bagian Selatan|Area Lampung|Kemiling
Sumatera Bagian Selatan|Area Lampung|Antasari
Banten|Area Serang|Kramatwatu
Banten|Area Serang|Pandeglang
Banten|Area Serang|Ciruas
Banten|Area Serang|Cijawa Masjid
Banten|Area Cilegon|Simpang Tiga
Banten|Area Cilegon|Ruko PCI
Banten|Area Cilegon|Jombang
Banten|Area Tangerang Kota 2|Veteran Tangerang
Banten|Area Tangerang Kota 2|Banjar Wijaya
Banten|Area Tangerang Kota 2|Sangiang
Banten|Area Tangerang Kota 2|Perumnas 2 Tng
Banten|Area Tangerang Kota 2|Karawaci
Banten|Area Tangerang Kota 2|Cikupa
Megapolitan Barat 1|Area Tangerang Kota 1|Ciledug
Megapolitan Barat 1|Area Tangerang Kota 1|Puri Beta Larangan
Megapolitan Barat 1|Area Tangerang Kota 1|Karang Tengah
Megapolitan Barat 1|Area Tangerang Kota 1|Pinang
Megapolitan Barat 1|Area Tangerang Kota 1|Graha Raya
Megapolitan Barat 1|Area Jakarta Barat 1|Cengkareng
Megapolitan Barat 1|Area Jakarta Barat 1|Duri Kosambi
Megapolitan Barat 1|Area Jakarta Barat 1|Meruya Ilir
Megapolitan Barat 1|Area Jakarta Barat 1|Meruya Selatan
Megapolitan Barat 1|Area Jakarta Barat 1|Ceger Pjmi
Megapolitan Barat 1|Area Jakarta Barat 1|Pesanggrahan
Megapolitan Barat 2|Area Jakarta Barat 2|Palmerah
Megapolitan Barat 2|Area Jakarta Barat 2|Tanjung Duren
Megapolitan Barat 2|Area Jakarta Barat 2|Tomang
Megapolitan Barat 2|Area Jakarta Barat 2|Kebon Jeruk
Megapolitan Barat 2|Area Tangerang Selatan 1|Pangkalan Jati
Megapolitan Barat 2|Area Tangerang Selatan 1|Ciputat
Megapolitan Barat 2|Area Tangerang Selatan 1|Merpati
Megapolitan Barat 2|Area Tangerang Selatan 1|Cirendeu
Megapolitan Barat 2|Area Tangerang Selatan 2|Pamulang 1
Megapolitan Barat 2|Area Tangerang Selatan 2|Pamulang 2
Megapolitan Barat 2|Area Tangerang Selatan 2|BSD Boulevard
Megapolitan Barat 2|Area Tangerang Selatan 2|Cisauk
Megapolitan Selatan|Area Jakarta Selatan 2|Bintaro
Megapolitan Selatan|Area Jakarta Selatan 2|Radio Dalam
Megapolitan Selatan|Area Jakarta Selatan 2|Mampang
Megapolitan Selatan|Area Jakarta Selatan 2|Taman Margasatwa
Megapolitan Selatan|Area Jakarta Selatan 2|Pasar Minggu
Megapolitan Selatan|Area Jakarta Selatan 1|Tebet
Megapolitan Selatan|Area Jakarta Selatan 1|Condet
Megapolitan Selatan|Area Jakarta Selatan 1|Halim
Megapolitan Selatan|Area Jakarta Selatan 1|Hek Kramat Jati
Megapolitan Selatan|Area Jakarta Selatan 1|Tanah Merdeka
Megapolitan Utara|Area Utara 1|Salemba
Megapolitan Utara|Area Utara 1|Kampung Melayu
Megapolitan Utara|Area Utara 1|Kramat Asem
Megapolitan Utara|Area Utara 1|Pangkalan Asem
Megapolitan Utara|Area Utara 1|Cempaka
Megapolitan Utara|Area Utara 2|Kemayoran
Megapolitan Utara|Area Utara 2|Sumur Batu (Sunter Jaya)
Megapolitan Utara|Area Utara 2|Rawa Badak
Megapolitan Utara|Area Utara 2|Kramat Jaya
Megapolitan Utara|Area Utara 2|Kebon Bawang
Megapolitan Timur|Area Jakarta Timur 1|Rawamangun
Megapolitan Timur|Area Jakarta Timur 1|Buaran
Megapolitan Timur|Area Jakarta Timur 1|Perumnas Klender
Megapolitan Timur|Area Jakarta Timur 1|Penggilingan
Megapolitan Timur|Area Jakarta Timur 1|Pulo Gebang
Megapolitan Timur|Area Jakarta Timur 2|Cipinang
Megapolitan Timur|Area Jakarta Timur 2|Pondok Bambu
Megapolitan Timur|Area Jakarta Timur 2|Radin Inten
Megapolitan Timur|Area Jakarta Timur 2|Pondok Kelapa
Megapolitan Timur|Area Jakarta Timur 2|Bintara
Megapolitan Timur Plus|Area Akses UI|Akses UI
Megapolitan Timur Plus|Area Akses UI|Ciganjur
Megapolitan Timur Plus|Area Akses UI|Jagakarsa
Megapolitan Timur Plus|Area Cibubur|Kalisari
Megapolitan Timur Plus|Area Cibubur|Cibubur
Megapolitan Timur Plus|Area Cibubur|Ciracas
Megapolitan Timur Plus|Area Kranggan|Jati Rangon
Megapolitan Timur Plus|Area Kranggan|Cilangkap
Megapolitan Timur Plus|Area Kranggan|Kranggan
Megapolitan Timur Plus|Area Kranggan|Cikeas
Bekasi Plus|Area Jati Bekasi|Jatibening
Bekasi Plus|Area Jati Bekasi|Jatiwaringin
Bekasi Plus|Area Jati Bekasi|Pondok Gede
Bekasi Plus|Area Jati Bekasi|Jatimekar
Bekasi Plus|Area Jati Bekasi|Jatiwarna
Bekasi Plus|Area Jati Bekasi|Jatisari
Bekasi Plus|Area Kabupaten Bogor|Vila Nusa Indah
Bekasi Plus|Area Kabupaten Bogor|Bekasi Timur Regency
Bekasi Plus|Area Kabupaten Bogor|Mustika Jaya
Bekasi Plus|Area Kabupaten Bogor|Graha Mustika Media
Bekasi Plus|Area Kabupaten Bogor|Limus Pratama
Bekasi Plus|Area Kabupaten Bogor|Metland Transyogi
Bekasi Kota|Bekasi Kota 1|Jati Mulya
Bekasi Kota|Bekasi Kota 1|Narogong
Bekasi Kota|Bekasi Kota 1|Rawalumbu
Bekasi Kota|Bekasi Kota 1|Galaxy
Bekasi Kota|Bekasi Kota 2|Harapan Jaya
Bekasi Kota|Bekasi Kota 2|Taman Harapan Baru
Bekasi Kota|Bekasi Kota 2|Sektor 5
Bekasi Kota|Bekasi Kota 3|Agus Salim
Bekasi Kota|Bekasi Kota 3|Kayuringin
Bekasi Kota|Bekasi Kota 3|Villa Indah Permai
Bekasi Kota|Bekasi Kota 3|Taman Wisma Asri
Jabartara|Jabartara 1|Perumnas 3
Jabartara|Jabartara 1|Alamanda
Jabartara|Jabartara 1|Graha Prima
Jabartara|Jabartara 1|Mangun Jaya
Jabartara|Jabartara 2|Cibitung
Jabartara|Jabartara 2|Tambun
Jabartara|Jabartara 2|Metland Cibitung
Jabartara|Jabartara 3|Cikarang Pilar
Jabartara|Jabartara 3|Cikarang Jababeka
Jabartara|Jabartara 3|Lippo Cikarang
Jabartara|Jabartara 3|Karawang
Bogor Plus|Area Bogor 1|Paledang
Bogor Plus|Area Bogor 1|Ciomas
Bogor Plus|Area Bogor 1|Sumeru
Bogor Plus|Area Bogor 1|RA Kosasih Sukabumi
Bogor Plus|Area Bogor 2|Bangbarung
Bogor Plus|Area Bogor 2|Atang Senjaya
Bogor Plus|Area Bogor 2|Pomad
Bogor Plus|Area Bogor 3|Karadenan
Bogor Plus|Area Bogor 3|Bojong Gede
Bogor Plus|Area Bogor 3|Cikaret
Bandung Raya|Area Bandung 1|Cihanjuang
Bandung Raya|Area Bandung 1|Sangkuriang
Bandung Raya|Area Bandung 1|Kopo
Bandung Raya|Area Bandung 1|Cijerah
Bandung Raya|Area Bandung 2|Sumbawa
Bandung Raya|Area Bandung 2|Ujung Berung
Bandung Raya|Area Bandung 2|Antapani
Bandung Raya|Area Bandung 2|Pahlawan
Bandung Raya|Area Jabar Kembang|Tasikmalaya
Bandung Raya|Area Jabar Kembang|Garut
Bandung Raya|Area Jabar Kembang|Buah Batu
Bandung Raya|Area Jabar Kembang|Margahayu
Jatijaya|Area Pantura Tengah|Purwokerto
Jatijaya|Area Pantura Tengah|Tegal
Jatijaya|Area Pantura Tengah|Tuparev
Jatijaya|Area Joglosemar|Kartasura
Jatijaya|Area Joglosemar|Surakarta
Jatijaya|Area Joglosemar|Semarang
Jatijaya|Area Joglosemar|AM Sangaji
Jatijaya|Area Jawa Timur|Sidoarjo
Jatijaya|Area Jawa Timur|SMA Komplek
Jatijaya|Area Jawa Timur|Gayungsari
Jatijaya|Area Jawa Timur|Rungkut
Jatijaya|Area Jawa Timur|Malang
""".strip()


_LOCATION_CODE_TEXT = """
278|Merduati
287|Jambo Tape
132|Medan Baru
133|Medan Helvetia
285|Medan Area
286|Medan Johor
239|Tanjung Datuk
259|Panam
289|Hangtuah
257|Bukit Tinggi
277|Payakumbuh
162|Punti Kayu
163|Sukamto
165|Sudirman
288|The Hok
290|Telanai Jambi
293|Way Halim
294|Metro
295|Rajabasa
298|Pahoman
299|Kemiling
205|Antasari
187|Kramatwatu
197|Pandeglang
256|Ciruas
148|Cijawa Masjid
185|Simpang Tiga
186|Ruko PCI
193|Jombang
141|Veteran Tangerang
142|Perumnas 2 Tng
249|Sangiang
250|Banjar Wijaya
140|Karawaci
262|Cikupa
127|Cengkareng
128|Pesanggrahan
129|Meruya Ilir
152|Ciledug
178|Puri Beta Larangan
179|Ceger Pjmi
184|Karang Tengah
189|Pinang
227|Meruya Selatan
254|Graha Raya
261|Duri Kosambi
103|Pangkalan Jati
108|Palmerah
171|Ciputat
177|Pamulang 2
196|Pamulang 1
212|Cisauk
226|Kebon Jeruk
228|Tanjung Duren
229|Tomang
248|BSD Boulevard
252|Cirendeu
255|Merpati
101|Taman Margasatwa
106|Hek Kramat Jati
107|Mampang
109|Pasar Minggu
110|Bintaro
168|Halim
169|Tanah Merdeka
192|Condet
216|Radio Dalam
219|Tebet
102|Cempaka
113|Rawa Badak
117|Kampung Melayu
157|Kramat Jaya
173|Salemba
175|Kramat Asem
176|Pangkalan Asem
194|Kemayoran
201|Sumur Batu (Sunter Jaya)
203|Kebon Bawang
105|Buaran
111|Pondok Kelapa
112|Pondok Bambu
115|Rawamangun
130|Bintara
174|Cipinang
183|Perumnas Klender
188|Radin Inten
202|Penggilingan
204|Pulo Gebang
116|Ciracas
118|Akses UI
126|Cibubur
146|Cikeas
153|Kranggan
160|Ciganjur
167|Cilangkap
195|Kalisari
218|Jagakarsa
269|Jati Rangon
119|Jatimekar
122|Vila Nusa Indah
123|Jatiwarna
147|Jatisari
151|Jatiwaringin
154|Mustika Jaya
158|Pondok Gede
223|Graha Mustika Media
225|Metland Transyogi
234|Limus Pratama
270|Jatibening
274|Bekasi Timur Regency
120|Rawalumbu
121|Taman Harapan Baru
143|Kayuringin
144|Agus Salim
155|Harapan Jaya
159|Galaxy
211|Villa Indah Permai
265|Taman Wisma Asri
267|Sektor 5
271|Jati Mulya
273|Narogong
124|Tambun
156|Cibitung
224|Lippo Cikarang
242|Metland Cibitung
263|Graha Prima
264|Karawang
266|Mangun Jaya
268|Alamanda
272|Perumnas 3
275|Cikarang Pilar
276|Cikarang Jababeka
145|Sumeru
149|Paledang
190|Bojong Gede
191|Pomad
199|Ciomas
230|Karadenan
231|RA Kosasih Sukabumi
232|Atang Senjaya
233|Bangbarung
235|Cikaret
134|Cihanjuang
135|Buah Batu
136|Sumbawa
137|Ujung Berung
138|Sangkuriang
210|Kopo
236|Garut
237|Tasikmalaya
279|Antapani
280|Margahayu
282|Pahlawan
283|Cijerah
131|Malang
180|SMA Komplek
181|Gayungsari
182|Tuparev
198|Rungkut
244|Surakarta
245|Semarang
246|Kartasura
260|AM Sangaji
284|Tegal
291|Sidoarjo
292|Purwokerto
""".strip()


ORGANIZATION_ROWS = tuple(tuple(line.split("|", 2)) for line in _MASTER_TEXT.splitlines())
REGIONS = tuple(dict.fromkeys(region for region, _, _ in ORGANIZATION_ROWS))
LOCATION_SCOPE = {location.casefold(): (region, area) for region, area, location in ORGANIZATION_ROWS}
LOCATION_CODE_BY_NAME = {
    location.casefold(): code
    for code, location in (line.split("|", 1) for line in _LOCATION_CODE_TEXT.splitlines())
}
LOCATION_BY_CODE = {
    code: location
    for code, location in (line.split("|", 1) for line in _LOCATION_CODE_TEXT.splitlines())
}
ORGANIZATION_CODE_ROWS = tuple(
    (LOCATION_CODE_BY_NAME[location.casefold()], region, area, location)
    for region, area, location in ORGANIZATION_ROWS
)

# Nama lama dari deck tetap diterima agar data historis ikut dimigrasikan.
LOCATION_ALIASES = {
    "lampaseh": "Merduati",
    "cijawa serang": "Cijawa Masjid",
    "jombang cilegon": "Jombang",
    "hek-kramat jati": "Hek Kramat Jati",
}

REGIONAL_ACCOUNTS = {
    "sumbagut": "Sumatera Bagian Utara",
    "sumbagsel": "Sumatera Bagian Selatan",
    "banten": "Banten",
    "mega_barat1": "Megapolitan Barat 1",
    "mega_barat2": "Megapolitan Barat 2",
    "mega_selatan": "Megapolitan Selatan",
    "mega_utara": "Megapolitan Utara",
    "mega_timur": "Megapolitan Timur",
    "mega_timur_plus": "Megapolitan Timur Plus",
    "bekasi_plus": "Bekasi Plus",
    "bekasi_kota": "Bekasi Kota",
    "jabartara": "Jabartara",
    "bogor_plus": "Bogor Plus",
    "bandung_raya": "Bandung Raya",
    "jatijaya": "Jatijaya",
}


def _clean_location_key(value: object) -> str:
    key = str(value or "").strip()
    if key.endswith(".0") and key[:-2].isdigit():
        key = key[:-2]
    return key


def resolve_location(value: object) -> tuple[str, str, str, str]:
    """Kembalikan (kode, lokasi, wilayah, area) untuk kode SIL maupun nama lokasi."""
    key = _clean_location_key(value)
    location = LOCATION_BY_CODE.get(key)
    if not location:
        location = LOCATION_ALIASES.get(key.casefold(), key)
    scope = LOCATION_SCOPE.get(location.casefold())
    if not scope:
        return "", key, "Belum Dipetakan", "Belum Dipetakan"
    region, area = scope
    return LOCATION_CODE_BY_NAME[location.casefold()], location, region, area


def scope_for_location(location: object) -> tuple[str, str]:
    """Kembalikan (wilayah, area) dari kode SIL atau nama lokasi."""
    _, _, region, area = resolve_location(location)
    return region, area


def location_code_for_name(location: object) -> str:
    return resolve_location(location)[0]


def areas_for_region(region: str) -> list[str]:
    return sorted({area for item_region, area, _ in ORGANIZATION_ROWS if item_region == region})


def locations_for_scope(region: str = "", area: str = "") -> list[str]:
    return sorted(
        location
        for item_region, item_area, location in ORGANIZATION_ROWS
        if (not region or item_region == region) and (not area or item_area == area)
    )
