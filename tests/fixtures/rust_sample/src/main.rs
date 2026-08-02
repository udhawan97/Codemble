mod render;
mod util;

use crate::util::{helper, Formatter, Mode};
use render::Render;

fn main() {
    let formatter = Formatter::new("out: ");
    let banner = formatter.render();
    println!("{}", banner);
    match helper(&Mode::Loud) {
        Ok(text) => println!("{}", text),
        Err(error) => eprintln!("{}", error),
    }
}

#[test]
fn main_reports_failures() {
    assert!(helper(&Mode::Plain).is_ok());
}
