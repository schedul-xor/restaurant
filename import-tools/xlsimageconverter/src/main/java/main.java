import com.google.common.io.Files;
import org.apache.commons.codec.binary.Base64;
import org.apache.poi.openxml4j.exceptions.InvalidFormatException;
import org.apache.poi.openxml4j.util.ZipSecureFile;
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

        ZipSecureFile.setMinInflateRatio(0); // Ignore zip bomb reduction

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

                for (int li = 1; li <= s.getLastRowNum(); li++) {
                    String posKey = si + "/" + li;

                    Row r = s.getRow(li);
                    if (r == null) {
                        continue;
                    }

                    String title = null;
                    try {
                        Cell c0 = r.getCell(3);
                        if (c0.getCellTypeEnum() != CellType.STRING) {
                            log.warn("  l67 should be string not {}", c0.getCellTypeEnum());
                            continue;
                        }

                        title = c0.getStringCellValue().trim();
                    } catch (Exception e) {
                        log.error("   {} {}", li, e);
                    }

                    // Used as content
                    String explicitCategoryName = "";
                    try {
                        Cell c0 = r.getCell(4);
                        if (c0 == null || c0.getCellTypeEnum() == CellType.BLANK) {
                            explicitCategoryName = "";
                        } else if (c0.getCellTypeEnum() != CellType.STRING) {
                            log.warn("  l81 should be string not  {}", c0.getCellTypeEnum());
                            continue;
                        } else {
                            explicitCategoryName = c0.getStringCellValue().trim();
                        }
                    } catch (Exception e) {
                        log.error("   {} {}", li, e);
                    }

                    // Used as serial ID
                    String serialId = "";
                    try {
                        Cell c0 = r.getCell(5);
                        if (c0.getCellTypeEnum() != CellType.STRING) {
                            log.warn("  l110 should be string not  {}", c0.getCellTypeEnum());
                            continue;
                        }

                        serialId = c0.getStringCellValue().trim();
                    } catch (Exception e) {
                        log.error("   {} {}", li, e);
                    }

                    // URL
                    String url = "";
                    try {
                        Cell c0 = r.getCell(6);
                        if (c0.getCellTypeEnum() != CellType.STRING) {
                            log.warn("  l110 should be string not  {}", c0.getCellTypeEnum());
                            continue;
                        }

                        url = c0.getStringCellValue().trim();
                    } catch (Exception e) {
                        log.error("   {} {}", li, e);
                    }

                    double latitude = 0, longitude = 0;

                    FoundRow fr = new FoundRow();
                    fr.name = title;
                    fr.latitude = latitude;
                    fr.longitude = longitude;
                    fr.buildingName = url;
                    fr.floorName = serialId;
                    fr.explicitCategoryName = explicitCategoryName;
                    fr.budget = url;
                    fr.categories.add(1);
                    foundRows.put(posKey, fr);
                }

                break;
            }
        } catch (IOException e) {
            e.printStackTrace();
        } catch (InvalidFormatException e) {
            e.printStackTrace();
        }

        JSONObject bodyObj = new JSONObject();
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

                    FileOutputStream streamWriter = new FileOutputStream(tmpTiffFile);
                    streamWriter.write(pdata.getData());
                    streamWriter.flush();
                    streamWriter.close();

                    BufferedImage image = ImageIO.read(tmpTiffFile);
                    BufferedImage tmp = new BufferedImage(image.getWidth(), image.getHeight(), BufferedImage.TYPE_INT_RGB);
                    Graphics2D off = tmp.createGraphics();
                    off.drawImage(image, 0, 0, Color.WHITE, null);

                    log.info("  Conv {} -> {} {}x{}", tmpTiffFile.getAbsolutePath(), tmpJpgFile.getAbsolutePath(), image.getWidth(), image.getHeight());

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
            bodyObj.put(posKey, obj);
        }

        File outputFile = new File(outputFilePath);
        try {
            FileWriter fw = new FileWriter(outputFile);
            fw.write(bodyObj.toString());
            fw.flush();
            fw.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}
