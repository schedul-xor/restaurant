import com.google.common.io.Files;
import org.apache.commons.codec.binary.Base64;
import org.apache.poi.openxml4j.exceptions.InvalidFormatException;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.ss.usermodel.Shape;
import org.json.JSONObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.Color;
import java.awt.image.BufferedImage;
import java.io.*;
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

                try {
                    File tmpTiffFile = File.createTempFile("tmptiff", "."+pdata.suggestFileExtension());
                    File tmpJpgFile = File.createTempFile("tmpjpg", ".jpg");

                    log.info("  Conv {} -> {}",tmpTiffFile.getAbsolutePath(),tmpJpgFile.getAbsolutePath());

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
