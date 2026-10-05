package controller;
public class TransactionManager {
    // BENCHMARK_DEPENDENCIES
    public String submit(String input) { int amount = Integer.parseInt(input); int fee = amount > 100 ? amount / 10 : 5; return "INSERT INTO ledger(fee) VALUES (" + fee + ")"; }

}
