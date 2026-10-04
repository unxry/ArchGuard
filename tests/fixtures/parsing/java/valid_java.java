package example;

import java.util.List;

@interface Audited {}
interface Store<T> { T find(); }
enum State { READY, DONE }

@Audited
public class Order<T> implements Store<T> {
    private final T value;
    private List<T> history;

    public Order(T value) { this.value = value; }

    @Override
    public T find() { return value; }
}
