using Acme.Core;
using Xunit;

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
