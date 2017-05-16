import org.apache.poi.openxml4j.exceptions.InvalidFormatException;
import org.apache.poi.ss.usermodel.*;
import org.json.JSONObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.*;
import java.util.*;

public class main {
    static final Logger log = LoggerFactory.getLogger(main.class);

    static public void main(String[] argv) {
        String xlsFilePath = argv[0];
        String outputFilePath = argv[1];

        File xlsFile = new File(xlsFilePath);

        log.info("Parse {}", xlsFile.getAbsolutePath());

        Map<String, Picture> pictureShapes = new HashMap<>();
        Map<String, FoundRow> foundRows = new HashMap<>();

        try {
            Workbook book = WorkbookFactory.create(xlsFile);

            for (int si = 0; si < book.getNumberOfSheets(); si++) {
                Sheet s = book.getSheetAt(si);
                log.info("  Sheet {} {} l{}->{}", si, s.getSheetName(), s.getFirstRowNum(), s.getLastRowNum());

                for (Shape shp : s.getDrawingPatriarch()) {
                    Picture pict = (Picture) shp;
                    int anchorRow = pict.getClientAnchor().getRow1();

                    String posKey = si + "/" + anchorRow;

                    pictureShapes.put(posKey, pict);
                }

                for (int li = 7; li < s.getLastRowNum(); li++) {
                    String posKey = si + "/" + li;

                    Row r = s.getRow(li);
                    if (r == null) {
                        continue;
                    }

                    String title = null;
                    try {
                        Cell c0 = r.getCell(0);
                        if (c0.getCellTypeEnum() != CellType.STRING) {
                            continue;
                        }

                        title = c0.getStringCellValue();
                        log.info("   {} {}", li, title);
                    } catch (Exception e) {
                        log.error("   {} {}", li, e);
                    }

                    double latitude = 0, longitude = 0;
                    try {
                        Cell c1 = r.getCell(1);
                        if (c1.getCellTypeEnum() != CellType.NUMERIC) {
                            continue;
                        }

                        latitude = c1.getNumericCellValue();
                    } catch (Exception e) {
                        log.error("   {} {}", li, e);
                    }
                    try {
                        Cell c2 = r.getCell(2);
                        if (c2.getCellTypeEnum() != CellType.NUMERIC) {
                            continue;
                        }

                        longitude = c2.getNumericCellValue();
                    } catch (Exception e) {
                        log.error("   {} {}", li, e);
                    }

                    FoundRow fr = new FoundRow();
                    fr.name = title;
                    fr.latitude = latitude;
                    fr.longitude = longitude;
                    foundRows.put(posKey, fr);
                }

                break;
            }
        } catch (IOException e) {
            e.printStackTrace();
        } catch (InvalidFormatException e) {
            e.printStackTrace();
        }

        JSONObject rootObj = new JSONObject();
        for (String posKey : foundRows.keySet()) {
            FoundRow fr = foundRows.get(posKey);

            String imgBase64 = null;
            String imgMime = null;
            if (pictureShapes.containsKey(posKey)) {
                Picture pict = pictureShapes.get(posKey);
                PictureData pdata = pict.getPictureData();
                imgBase64 = new String(Base64.getEncoder().encode(pdata.getData()));
                imgMime = pdata.getMimeType();
            }

            JSONObject obj = new JSONObject();
            obj.put("latitude", fr.latitude);
            obj.put("longitude", fr.longitude);
            obj.put("name", fr.name);
            obj.put("img_base64", imgBase64);
            obj.put("img_mime", imgMime);
            rootObj.put(posKey, obj);
        }

        File outputFile = new File(outputFilePath);
        try {
            FileWriter fw = new FileWriter(outputFile);
            fw.write(rootObj.toString());
            fw.flush();
            fw.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}
