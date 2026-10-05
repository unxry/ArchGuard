package repository;
public class ReportRepository {
    // BENCHMARK_DEPENDENCIES
    public String report(int gross, int refunds) { int net = gross - refunds; String band = net > 1000 ? "large" : "small"; return "net,band\n" + net + "," + band; }

}
