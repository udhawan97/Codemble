use crate::render::Render;
use std::fmt::Write;

pub enum Mode {
    Plain,
    Loud,
}

pub struct Formatter {
    pub prefix: String,
}

impl Formatter {
    pub fn new(prefix: &str) -> Self {
        Formatter {
            prefix: prefix.to_string(),
        }
    }

    pub fn set_prefix(&mut self, prefix: &str) {
        self.prefix = prefix.to_string();
    }

    fn decorate(&self, value: &str) -> String {
        let mut out = String::new();
        let _ = write!(out, "{}{}", self.prefix, value);
        out
    }
}

impl Render for Formatter {
    fn render(&self) -> String {
        self.decorate("body")
    }
}

pub mod text {
    pub fn shout(value: &str) -> String {
        value.to_uppercase()
    }
}

pub fn helper(mode: &Mode) -> Result<String, String> {
    let text = normalize("  raw  ")?;
    match mode {
        Mode::Plain => Ok(text),
        Mode::Loud => Ok(text::shout(&text)),
    }
}

pub fn normalize(value: &str) -> Result<String, String> {
    Ok(value.trim().to_string())
}
