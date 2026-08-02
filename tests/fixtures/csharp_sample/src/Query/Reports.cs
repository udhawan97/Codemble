using System.Collections.Generic;
using System.Linq;

namespace Acme.Query;

public static class Reports
{
    public static IEnumerable<string> Recent(List<string> items)
    {
        var picked = from item in items
                     where item.Length > 2
                     select item;
        return picked.ToList();
    }

    public static string Describe(int code) => code switch
    {
        0 => "empty",
        _ => "filled",
    };

    public static int Twice(this int value) => value * 2;

    public static T FirstOrSelf<T>(List<T> values) where T : class => values[0];
}
