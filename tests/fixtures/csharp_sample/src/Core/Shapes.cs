namespace Acme.Core
{
    public readonly struct Point
    {
        public Point(int x)
        {
            X = x;
        }

        public int X { get; }

        public Point Shift(int by) => new Point(X + by);
    }
}
