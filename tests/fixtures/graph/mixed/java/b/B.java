package sample.b;
import sample.c.C;
// GRAPH_PRIVATE_SOURCE_MARKER
public class B {
    public static void run() { C.ping(); C.ping(); B.ping(); }
    public static void ping() {}
}
