/**
 * FEWS Dana Masuk - Google Apps Script
 * Sheet wajib: Cabang, Mutasi, Matching
 */

function normalizeText(value) {
  if (!value) return "";
  return String(value)
    .toUpperCase()
    .replace(/[^A-Z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function similarity(a, b) {
  a = normalizeText(a);
  b = normalizeText(b);
  if (!a || !b) return 0;
  var maxLen = Math.max(a.length, b.length);
  if (maxLen === 0) return 100;
  var distance = levenshtein(a, b);
  return ((maxLen - distance) / maxLen) * 100;
}

function levenshtein(a, b) {
  var matrix = [];
  for (var i = 0; i <= b.length; i++) matrix[i] = [i];
  for (var j = 0; j <= a.length; j++) matrix[0][j] = j;
  for (i = 1; i <= b.length; i++) {
    for (j = 1; j <= a.length; j++) {
      if (b.charAt(i - 1) === a.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j] + 1
        );
      }
    }
  }
  return matrix[b.length][a.length];
}

function daysDiff(d1, d2) {
  var ms = Math.abs(new Date(d1).getTime() - new Date(d2).getTime());
  return Math.round(ms / (1000 * 60 * 60 * 24));
}

function runFEWSMatching() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var cabang = ss.getSheetByName("Cabang");
  var mutasi = ss.getSheetByName("Mutasi");
  var matching = ss.getSheetByName("Matching");

  var cabangData = cabang.getDataRange().getValues();
  var mutasiData = mutasi.getDataRange().getValues();

  var out = [["Branch ID", "Mutasi ID", "Status", "Risiko", "Jenis Ketidaksesuaian", "Similarity Nama", "Selisih Nominal", "Selisih Hari", "Confidence", "Ringkasan"]];
  var usedMutasi = {};

  for (var i = 1; i < cabangData.length; i++) {
    var c = cabangData[i];
    var branchId = c[0];
    var tglCabang = c[1];
    var namaCustomer = c[3];
    var nominalInput = Number(c[5] || 0);
    var invoice = normalizeText(c[7]);

    var best = null;

    for (var j = 1; j < mutasiData.length; j++) {
      var m = mutasiData[j];
      var mutasiId = m[0];
      if (usedMutasi[mutasiId]) continue;

      var tglMutasi = m[1];
      var namaPengirim = m[2];
      var nominalMasuk = Number(m[3] || 0);
      var desc = normalizeText(m[5]);

      var sim = similarity(namaCustomer, namaPengirim);
      var gapNominal = Math.abs(nominalInput - nominalMasuk);
      var gapHari = daysDiff(tglCabang, tglMutasi);
      var invoiceHit = invoice && desc.indexOf(invoice) >= 0;

      var score = (sim * 0.35) + Math.max(0, 40 - (gapNominal / 500)) + Math.max(0, 25 - (gapHari * 7)) + (invoiceHit ? 25 : 0);

      if (!best || score > best.score) {
        best = {
          mutasiId: mutasiId,
          sim: sim,
          gapNominal: gapNominal,
          gapHari: gapHari,
          score: score,
          invoiceHit: invoiceHit
        };
      }
    }

    if (!best) {
      out.push([branchId, "", "UNMATCHED", 4, "Belum Masuk", 0, nominalInput, "", 0, "Input cabang belum ditemukan di mutasi"]);
      continue;
    }

    var status = "UNMATCHED";
    if ((best.gapNominal === 0 && best.sim >= 85 && best.gapHari <= 2) || (best.invoiceHit && best.gapNominal <= 1000 && best.gapHari <= 2)) {
      status = "MATCHED";
    } else if (best.gapNominal <= 1000 && best.gapHari <= 2 && (best.sim >= 70 || best.invoiceHit)) {
      status = "NEED REVIEW";
    }

    var mismatch = [];
    var risk = 0;

    if (best.sim < 85) {
      mismatch.push("Nama Pengirim Berbeda");
      risk += 2;
    }
    if (best.gapNominal > 1000) {
      mismatch.push("Mismatch Nominal");
      risk += 3;
    } else if (best.gapNominal > 0) {
      mismatch.push("Nominal Selisih Kecil");
    }
    if (best.gapHari > 2) {
      mismatch.push("Tanggal Pembayaran Tidak Logis");
      risk += 3;
    }
    if (best.gapNominal === 100 || best.gapNominal === 500) {
      mismatch.push("Selisih Aneh +100/+500");
    }
    if (status === "MATCHED") {
      risk = 0;
      if (mismatch.length === 0) mismatch.push("Nominal dan identitas sesuai");
    }

    out.push([
      branchId,
      best.mutasiId,
      status,
      risk,
      mismatch.join(", "),
      Number(best.sim.toFixed(2)),
      best.gapNominal,
      best.gapHari,
      Number(Math.max(0, Math.min(100, best.score)).toFixed(2)),
      "Nama " + best.sim.toFixed(1) + "% | Gap " + best.gapNominal + " | Hari " + best.gapHari
    ]);

    usedMutasi[best.mutasiId] = true;
  }

  for (var k = 1; k < mutasiData.length; k++) {
    var mm = mutasiData[k];
    var mutasiId2 = mm[0];
    if (usedMutasi[mutasiId2]) continue;
    out.push(["", mutasiId2, "UNMATCHED", 4, "Tidak Diinput", 0, Number(mm[3] || 0), "", 0, "Dana masuk tidak ditemukan pada input cabang"]);
  }

  matching.clearContents();
  matching.getRange(1, 1, out.length, out[0].length).setValues(out);
}

function onEdit(e) {
  var sheetName = e && e.range && e.range.getSheet().getName();
  if (sheetName === "Cabang" || sheetName === "Mutasi") {
    runFEWSMatching();
  }
}
