package sample.c;
import sample.a.A;
// GRAPH_PRIVATE_SOURCE_MARKER
public class C {
    public static void run() { A.ping(); A.ping(); C.ping(); }
    public static void ping() {}
}
