using Acme.Core;

namespace Acme.Tests;

public class StoreTests
{
    [Fact]
    public void SavesWithoutThrowing()
    {
        var store = new MemoryStore();
        store.Save();
    }
}
