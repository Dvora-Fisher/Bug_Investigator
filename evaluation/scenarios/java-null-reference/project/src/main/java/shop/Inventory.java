package shop;

import java.util.HashMap;
import java.util.Map;

public class Inventory {
    private final Map<String, Integer> stock = new HashMap<>();

    public void receive(String sku, int quantity) {
        stock.merge(sku, quantity, Integer::sum);
    }

    /** Units available for a SKU; 0 for SKUs we have never stocked. */
    public int available(String sku) {
        return stock.get(sku);
    }

    public boolean canFulfil(String sku, int quantity) {
        return available(sku) >= quantity;
    }
}
