package resolve; import static resolve.Tools.ping; class App { void run(Tools unknown) { Tools.ping(1); ping(2); unknown.instance(); missing(); } }
