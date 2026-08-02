pub trait Render {
    fn render(&self) -> String;
}

pub async fn fetch<'a>(source: &'a str) -> Option<String> {
    let loaded = load(source).await;
    unsafe {
        touch();
    }
    loaded
}

pub fn render_all<T: Render>(items: &[T]) -> Vec<String> {
    let mut out = Vec::new();
    for item in items {
        out.push(item.render());
    }
    out
}

pub fn collect(items: &[String], out: &mut Vec<String>) {
    for item in items {
        out.push(item.clone());
    }
}

async fn load(source: &str) -> Option<String> {
    Some(source.to_string())
}

unsafe fn touch() {}
