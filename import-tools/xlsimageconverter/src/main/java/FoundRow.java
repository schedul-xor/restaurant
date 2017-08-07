import java.util.HashSet;
import java.util.Set;

/**
 * Created by xor on 17/05/16.
 */
public class FoundRow {
    public String name;
    public double latitude;
    public double longitude;
    public String buildingName;
    public String floorName;
    public String budget;
    public String explicitCategoryName;
    public Set<Integer> categories;

    public FoundRow() {
        categories = new HashSet<>();
    }
}
