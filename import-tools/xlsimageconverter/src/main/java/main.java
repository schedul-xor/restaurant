import com.google.common.io.Files;
import org.apache.commons.codec.binary.Base64;
import org.apache.poi.openxml4j.exceptions.InvalidFormatException;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.ss.usermodel.Shape;
import org.json.JSONArray;
import org.json.JSONObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.Color;
import java.awt.image.BufferedImage;
import java.io.*;
import java.text.Normalizer;
import java.util.*;

public class main {
    static final Logger log = LoggerFactory.getLogger(main.class);

    static public void main(String[] argv) {
        System.setProperty("it.geosolutions.imageio.tiff.lazy", "true");

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
                    try {
                        Picture pict = (Picture) shp;
                        int anchorRow = pict.getClientAnchor().getRow1();

                        String posKey = si + "/" + anchorRow;

                        pictureShapes.put(posKey, pict);
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                }

                // Category headers
                Map<Integer, String> categoryNames = new HashMap<>();
                Row headerRow = s.getRow(0);
                for (int c = 7; c < 255; c++) {
                    Cell c0 = headerRow.getCell(c);
                    if (c0 == null || c0.getCellTypeEnum() != CellType.STRING) {
                        break;
                    }
                    String categoryTitle = c0.getStringCellValue().trim();
                    log.info("Category title {}={}", c, categoryTitle);
                    categoryNames.put(c, categoryTitle);
                }

                for (int li = 2; li <= s.getLastRowNum(); li++) {
                    String posKey = si + "/" + li;

                    Row r = s.getRow(li);
                    if (r == null) {
                        continue;
                    }

                    String title = null;
                    try {
                        Cell c0 = r.getCell(2);
                        if (c0.getCellTypeEnum() != CellType.STRING) {
                            continue;
                        }

                        title = c0.getStringCellValue().trim();
//                        log.info("   {} {}", li, title);
                    } catch (Exception e) {
                        log.error("   {} {}", li, e);
                    }

                    String explicitCategoryName = null;
                    try {
                        Cell c0 = r.getCell(4);
                        if (c0.getCellTypeEnum() != CellType.STRING) {
                            continue;
                        }

                        explicitCategoryName = c0.getStringCellValue().trim();
//                        log.info("   {} {}", li, title);
                    } catch (Exception e) {
                        log.error("   {} {}", li, e);
                    }

                    String budget = null;
                    try {
                        Cell c0 = r.getCell(5);
                        if (c0.getCellTypeEnum() != CellType.STRING) {
                            continue;
                        }

                        budget = c0.getStringCellValue().trim();
//                        log.info("   {} {}", li, title);
                    } catch (Exception e) {
                        log.error("   {} {}", li, e);
                    }

                    String floorName = null;
                    try {
                        Cell c0 = r.getCell(1);
                        if (c0.getCellTypeEnum() != CellType.STRING) {
                            continue;
                        }

                        floorName = c0.getStringCellValue().trim();
                    } catch (Exception e) {
                        log.error("   {} {}", li, e);
                    }

                    String buildingName = null;
                    try {
                        Cell c0 = r.getCell(0);
                        if (c0.getCellTypeEnum() != CellType.STRING) {
                            continue;
                        }

                        buildingName = c0.getStringCellValue().trim();
                    } catch (Exception e) {
                        log.error("   {} {}", li, e);
                    }

                    double latitude = 0, longitude = 0;
                    Cell cl = r.getCell(6);
                    if (cl == null) {
                        continue;
                    }
                    String ll = Normalizer.normalize(cl.getStringCellValue(), Normalizer.Form.NFKC).trim();
                    if (ll.equals("")) {
                        continue;
                    }
                    String lla[] = ll.split("[\\s\\n]+");
                    latitude = Double.parseDouble(lla[0].trim());
                    longitude = Double.parseDouble(lla[1].trim());

//                    try {
//                        Cell c1 = r.getCell(1);
//                        if (c1.getCellTypeEnum() != CellType.NUMERIC) {
//                            continue;
//                        }
//
//                        latitude = c1.getNumericCellValue();
//                    } catch (Exception e) {
//                        log.error("   {} {}", li, e);
//                    }
//                    try {
//                        Cell c2 = r.getCell(2);
//                        if (c2.getCellTypeEnum() != CellType.NUMERIC) {
//                            continue;
//                        }
//
//                        longitude = c2.getNumericCellValue();
//                    } catch (Exception e) {
//                        log.error("   {} {}", li, e);
//                    }

                    FoundRow fr = new FoundRow();
                    fr.name = title;
                    fr.latitude = latitude;
                    fr.longitude = longitude;
                    fr.buildingName = buildingName;
                    fr.floorName = floorName;
                    fr.explicitCategoryName = explicitCategoryName;
                    fr.budget = budget;
                    for (Map.Entry<Integer, String> kv : categoryNames.entrySet()) {
                        Cell categoryCl = r.getCell(kv.getKey());
                        if (categoryCl == null) {
                            continue;
                        }
                        String check = categoryCl.getStringCellValue().trim();
                        if (check.equals("")) {
                            continue;
                        }
                        fr.categories.add(kv.getKey());
                    }
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
            if (fr.name == null) {
                continue;
            }

            String imgBase64 = null;
            String imgMime = null;
            if (pictureShapes.containsKey(posKey)) {
                Picture pict = pictureShapes.get(posKey);
                PictureData pdata = pict.getPictureData();

                try {
                    File tmpTiffFile = File.createTempFile("tmptiff", "." + pdata.suggestFileExtension());
                    File tmpJpgFile = File.createTempFile("tmpjpg", ".jpg");

                    log.info("  Conv {} -> {}", tmpTiffFile.getAbsolutePath(), tmpJpgFile.getAbsolutePath());

                    FileOutputStream streamWriter = new FileOutputStream(tmpTiffFile);
                    streamWriter.write(pdata.getData());
                    streamWriter.flush();
                    streamWriter.close();

                    BufferedImage image = ImageIO.read(tmpTiffFile);
                    BufferedImage tmp = new BufferedImage(image.getWidth(), image.getHeight(), BufferedImage.TYPE_INT_RGB);
                    Graphics2D off = tmp.createGraphics();
                    off.drawImage(image, 0, 0, Color.WHITE, null);

                    ImageIO.write(tmp, "jpg", tmpJpgFile);

                    imgBase64 = new String(Base64.encodeBase64(Files.toByteArray(tmpJpgFile)));
                    imgMime = "image/jpeg";
                } catch (IOException e) {
                    e.printStackTrace();
                }
            }

            JSONObject obj = new JSONObject();
            obj.put("latitude", fr.latitude);
            obj.put("longitude", fr.longitude);
            obj.put("name", fr.name);
            obj.put("img_base64", imgBase64);
            obj.put("img_mime", imgMime);
            obj.put("budget", fr.budget);
            obj.put("building_name", fr.buildingName);
            obj.put("explicit_category_name", fr.explicitCategoryName);
            obj.put("floor_name", fr.floorName);

            JSONArray categoryIdsObj = new JSONArray();
            for (int categoryId : fr.categories) {
                categoryIdsObj.put(categoryId);
            }
            obj.put("category_ids", categoryIdsObj);
            log.info("   {} {} {}", fr.latitude, fr.longitude, fr.name);
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
