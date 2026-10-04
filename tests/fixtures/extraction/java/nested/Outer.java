package nested; @Deprecated public class Outer<T> { public static class Inner { int count; } interface Port {} Outer() {} <U> U identity(U x) { return x; } }
