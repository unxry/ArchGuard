package sample.a;
import sample.b.B;
// GRAPH_PRIVATE_SOURCE_MARKER
public class A {
    public static void run() { B.ping(); B.ping(); A.ping(); }
    public static void ping() {}
}
