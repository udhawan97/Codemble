using System.Collections.Generic;

namespace Acme.Core
{
    public interface IStore
    {
        void Save();
    }

    public class MemoryStore : IStore
    {
        private readonly List<string> _items = new List<string>();

        public int Count { get; private set; }

        public void Save()
        {
            Track("save");
        }

        private void Track(string action)
        {
            _items.Add(action);
        }
    }

    public record Person(string First, string? Last);

    public enum Color
    {
        Red,
        Green
    }
}
