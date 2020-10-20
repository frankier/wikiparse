#[macro_use] extern crate lazy_static;

use std::env;
use std::path::Path;
use std::str;
use std::fs::{create_dir_all, File};
use std::io::prelude::*;
use std::io::{self, BufReader};
use std::iter::Iterator;
use std::str::from_utf8;

use twoway::find_bytes;
use quick_xml::Reader;
use quick_xml::escape::unescape;
use quick_xml::events::Event;
use regex::bytes::Regex;

static FINNISH_TITLE: &[u8] = b"==Finnish==";
static SEP_CHARS: [char; 2] = [':', '/'];

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut reader = Reader::from_reader(BufReader::new(io::stdin()));
    reader.trim_text(true);
    let out_dir = Path::new(&args[1]);
    let mod_out_dir = out_dir.join("modules");
    let fin_out_dir = out_dir.join("fin");
    create_dir_all(&mod_out_dir).unwrap();
    create_dir_all(&fin_out_dir).unwrap();

    let mut title: Option<String> = None;
    let mut in_title = false;
    let mut in_revision = false;
    let mut in_text = false;
    let mut in_dbname = false;
    let mut in_timestamp = false;
    let mut count = 0;
    let mut revisions = 0;
    let mut buf = Vec::new();
    let mut dbname: Option<String> = None;
    let mut last_timestamp: String = String::from("0000-00-00T00:00:00Z");

    loop {
        match reader.read_event(&mut buf) {
            Ok(Event::Start(ref e)) => {
                match e.name() {
                    b"page" => {
                        revisions = 0;
                        count += 1;
                    }
                    b"title" => {
                        in_title = true;
                    }
                    b"revision" => {
                        in_revision = true;
                        revisions += 1;
                        if revisions > 1 {
                            panic!("More than one revision!?");
                        }
                    }
                    b"text" => {
                        in_text = true;
                    }
                    b"dbname" => {
                        in_dbname = true;
                    }
                    b"timestamp" => {
                        in_timestamp = true;
                    }
                    _ => (),
                }
            },
            Ok(Event::End(ref e)) => {
                match e.name() {
                    b"title" => {
                        in_title = false;
                    }
                    b"revision" => {
                        in_revision = false;
                    }
                    b"text" => {
                        in_text = false;
                    }
                    b"dbname" => {
                        in_dbname = false;
                    }
                    b"timestamp" => {
                        in_timestamp = false;
                    }
                    _ => (),
                }
            }
            Ok(Event::Text(e)) => {
                if in_revision && in_text {
                    let cur_out_dir;
                    let title_ref = title.as_ref().unwrap();
                    let start_idx;
                    let mut end_idx = None;
                    let escaped = e.escaped();
                    if title_ref.starts_with("Module:") {
                        start_idx = 0;
                        cur_out_dir = &mod_out_dir;
                    } else {
                        if title_ref.contains(&SEP_CHARS[..]) {
                            continue
                        }
                        cur_out_dir = &fin_out_dir;
                        lazy_static! {
                            static ref NEXT_TITLE_RE: Regex =
                                Regex::new("(?m)^==[^=]+==$").unwrap();
                        }
                        let fin_pos = find_bytes(escaped, FINNISH_TITLE);
                        if fin_pos.is_none() {
                            continue
                        }
                        start_idx = fin_pos.unwrap();
                        let fin_end = start_idx + FINNISH_TITLE.len();
                        match NEXT_TITLE_RE.find(&escaped[fin_end..]) {
                            Some(next_title_match) => end_idx = Some(fin_end + next_title_match.start()),
                            None => {}
                        }
                    }
                    let mut title_pathsafe = Vec::with_capacity(title_ref.len());
                    for c in title_ref.bytes() {
                        match c {
                            b'%' => title_pathsafe.extend(b"%25"),
                            b'/' => title_pathsafe.extend(b"%2F"),
                            _ => title_pathsafe.push(c)
                        }
                    }
                    let path = cur_out_dir.join(
                        from_utf8(title_pathsafe.as_ref()).unwrap()
                    );
                    let mut file = File::create(&path).unwrap();
                    let unescaped = unescape(&escaped[start_idx..end_idx.unwrap_or_else(|| escaped.len())]).unwrap();
                    file.write_all(&unescaped).unwrap();
                } else if in_title {
                    title = Some(e.unescape_and_decode_without_bom(&reader).unwrap());
                } else if in_dbname {
                    dbname = Some(e.unescape_and_decode_without_bom(&reader).unwrap());
                } else if in_timestamp {
                    let new_timestamp = e.escaped();
                    if new_timestamp > last_timestamp.as_bytes() {
                        last_timestamp.replace_range(.., str::from_utf8(&new_timestamp).unwrap());
                    }
                }
            }
            Ok(Event::Eof) => break,
            Err(e) => panic!("Error at position {}: {:?}", reader.buffer_position(), e),
            _ => (),
        }
    }
    println!("Got {:?}", count);
    let path = fin_out_dir.join("__metadata__.json");
    let mut file = File::create(&path).unwrap();
    write!(
        file,
        r#"{{"dbname": "{}", "last_timestamp": "{}"}}"#,
        dbname.unwrap(),
        last_timestamp
    ).unwrap();
}
