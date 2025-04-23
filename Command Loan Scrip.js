// ----- Configuration -----
const NEW_ISSUED_RANGE    = "A50:E100";  // New Issued Debt area (5 cols: A–E)
const EXISTING_DEBT_RANGE = "G50:M100";  // Existing Debt area (7 cols: G–M)

/**
 * Triggered on every edit in the spreadsheet.
 */
function onEdit(e) {
  const ss    = SpreadsheetApp.getActiveSpreadsheet();
  const sh    = e.range.getSheet();
  if (sh.getName() !== "Loan Input") return;
  if (e.range.getNumRows()!==1 || e.range.getNumColumns()!==1) {
    globalSync(); return;
  }
  
  const r = e.range.getRow(), c = e.range.getColumn();
  if (r<2||r>100||c>5) { globalSync(); return; }
  
  // Read A:E
  const rec = sh.getRange(r,1,1,5).getValues()[0];
  if (rec.some(v=>v===""||v==null)) { globalSync(); return; }
  const [debtID, debtAmt, rate, term, originYr] = rec.map((v,i)=> i<2? v:Number(v));
  
  // Annual payment (PMT)
  const annualPMT = Math.abs((debtAmt*rate)/(1 - Math.pow(1+rate,-term)));
  const expireYr  = originYr + term - 1;
  
  // Starting balance for each loop
  let startBal = debtAmt;
  
  for (let yr=originYr; yr<=expireYr; yr++) {
    const ws = ss.getSheetByName(String(yr));
    if (!ws) continue;
    
    // On origin sheet, write New Issued Debt
    if (yr===originYr) {
      updateRecordInSheet(ws, NEW_ISSUED_RANGE,
                          [debtID, debtAmt, rate, term], "new");
    }
    
    // Term remaining & period for PPMT
    const termRem = expireYr - yr + 1;
    const period  = yr - originYr + 1;
    
    // Write Existing Debt: [ID, startBal, rate, termRem, annualPMT]
    const rowWritten = updateRecordInSheet(ws, EXISTING_DEBT_RANGE,
                          [debtID, startBal, rate, termRem, annualPMT],
                          "existing", { period, originalTerm: term });
    
    // Flush and read back EOY balance (col M = startCol+6)
    SpreadsheetApp.flush();
    const sc = ws.getRange(EXISTING_DEBT_RANGE).getColumn();
    startBal = ws.getRange(rowWritten, sc+6).getValue();
  }
  
  globalSync();
}

/**
 * Writes or updates one record in a fixed area.
 * Returns the absolute row written.
 */
function updateRecordInSheet(sheet, rangeStr, dataVals, mode, opts={}) {
  const rng    = sheet.getRange(rangeStr);
  const arr    = rng.getValues();
  const sr     = rng.getRow();
  const sc     = rng.getColumn();
  const nCols  = rng.getNumColumns();
  const id     = String(dataVals[0]).trim();
  let   tRow   = findRecordRow(sheet, rangeStr, id);
  
  if (tRow===null) {
    // find blank
    for (let i=0;i<arr.length;i++){
      if (arr[i].every(v=>v===""||v===null)) {
        tRow = sr+i; break;
      }
    }
  }
  if (tRow===null) tRow = sr+arr.length; // append
  
  // Prepare placeholder row
  let full;
  if (mode==="new")      full = dataVals.concat([""]);      // 5 cols
  else if (mode==="existing") full = dataVals.concat(["",""]); //7 cols
  
  sheet.getRange(tRow, sc,1,nCols).setValues([full]);
  
  if (mode==="new") {
    // col E = sc+4 → =ABS(PMT(RC[-2],RC[-1],RC[-3]))
    sheet.getRange(tRow, sc+4)
         .setFormulaR1C1("=ABS(PMT(RC[-2],RC[-1],RC[-3]))");
  } else {
    // col L = sc+5 → PPMT: rate=RC[-3], period & nper constants, pv=RC[-4]
    const {period, originalTerm} = opts;
    const ppmf = `=ABS(PPMT(RC[-3],${period},${originalTerm},RC[-4]))`;
    sheet.getRange(tRow, sc+5).setFormulaR1C1(ppmf);
    // col M = sc+6 → =RC[-5]-RC[-1]
    sheet.getRange(tRow, sc+6)
         .setFormulaR1C1("=RC[-5]-RC[-1]");
  }
  return tRow;
}

/**
 * Finds a row by Debt ID in a fixed range, or null.
 */
function findRecordRow(sheet, rangeStr, debtID) {
  const rng = sheet.getRange(rangeStr);
  const arr = rng.getValues();
  const sr  = rng.getRow();
  for (let i=0;i<arr.length;i++){
    if (String(arr[i][0]).trim()===String(debtID).trim()) {
      return sr+i;
    }
  }
  return null;
}

/**
 * Clears any row in fixed areas whose Debt ID isn't in Loan Input.
 */
function globalSync() {
  const ss     = SpreadsheetApp.getActiveSpreadsheet();
  const valid  = getValidDebtIDs(ss.getSheetByName("Loan Input"));
  ss.getSheets().forEach(sh=>{
    if (!isNaN(Number(sh.getName()))) {
      ["A50:E100","G50:M100"].forEach(rng=>syncTableArea(sh,rng,valid));
    }
  });
}

/**
 * Clears rows where first cell nonblank & not in validIDs.
 */
function syncTableArea(sheet, rangeStr, validIDs) {
  const rng = sheet.getRange(rangeStr);
  const arr = rng.getValues();
  const sr  = rng.getRow();
  const sc  = rng.getColumn();
  const nc  = rng.getNumColumns();
  arr.forEach((row,i)=>{
    const id = String(row[0]).trim();
    if (id!=="" && !validIDs[id]) {
      sheet.getRange(sr+i,sc,1,nc).clearContent();
    }
  });
}

/**
 * Builds an object of valid Debt IDs from Loan Input A2:A100.
 */
function getValidDebtIDs(sheet) {
  return sheet.getRange("A2:A100").getValues()
    .reduce((o,[v])=>{
      if (v!==""&&v!=null) o[String(v).trim()]=true;
      return o;
    },{});
}
