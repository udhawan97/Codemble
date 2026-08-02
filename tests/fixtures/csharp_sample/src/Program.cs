using System;
using System.Text.Json;
using Acme.Core;
using Acme.Query;

namespace Acme.App;

public class Program
{
    private readonly IStore _store;

    public string Label { get; set; }

    public Program(IStore store)
    {
        _store = store;
    }

    public static async Task Main(string[] args)
    {
        var app = new Program(new MemoryStore());
        app.Run();
        await Task.Delay(1);
    }

    public void Run()
    {
        _store.Save();
        Describe();
        var store = new MemoryStore();
        store.Save();
    }

    private void Describe()
    {
        Console.WriteLine(Label);
    }
}
