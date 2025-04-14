# Convert between structured data formats

config-formats is a tool to convert between various structured data formats.

There are many formats that essentially model the same kind of data: nested structures of lists, maps, and simple types. This tool can convert between a few of them.

The list of supported formats can be displayed using `config-formats formats`:

 ID       Label          Extensions   Notes
 -------- -------------- ------------ ------------------------------------------
 json     JSON           .json
 toml     TOML           .toml        If the top level item is not a mapping,
                                      create a mapping with a key called
                                      "DEFAULT".
 msgpack  MessagePack    .msgpack
 ini      INI            .ini         Windows-Style INI files. Data is expected
                                      to be in the form {string : { string :
                                      string }}.
 sexp     S-Expression   .sexp        S-Expressions – very experimental
 python   Python         .py          Python literals. Does not executa
                                      arbitrary code ...
 pickle   Python Pickle  .pickle      Python pickle files. Reading is
                                      dangerous, as it can execute arbitrary
                                      code. Fails if a pickled class cannot be  
                                      found.
 edn      EDN            .edn
 hocon    HOCON          .hocon
 yaml     YAML           .yaml .yml   Supports almost any (even unsafe) data
                                      types. Reading is unsafe.
 env      .env           .env .envrc  .env files are essentially environment
                                      variable associations. Don’t expect
                                      roundtripping – complex values are not
                                      really supported, and variable names will
                                      be sanitized.

## Usage

Some format in, some format (by default YAML) out :-)

```sh
config-formats [options] [input-file [output-file]]
```

Options and arguments:

* `input-file` – the file to read from. If missing, read from stdin.
* `output-file` – the file to write to. If missing, write to stdout.
* `--from` _format_, `-f` _format_ – The source format. If not given, we try to guess the format from the input file extension, and if that does not work, auto-detection starts (see below)
* `--to` _format_, `-t` _format_ – The format to write to. If not given, guess from the output file extension, if that does not work, use YAML.
* `--pretty` / `--no-pretty` – Pretty-print the output. See below.
* `--simplify`, `-s` – force conversion to a limited set of data types.
* `-v`, `--verbose`; `-vv`, `--debug` – increase informational output on stderr.

## Exit codes

| 0 | everything went fine        |
| 1 | invalid command line etc.   |
| 2 | failed to read input file   |
| 3 | failed to write output file |

## Auto-detection

If the source format is neither specified using the `--from` option nor using the input file name’s suffix, the program tries to auto-detect the format. It does so by simply trying to parse the input using each of the formats in the order they are listed using `config-formats formats` and taking the first one that works without errors.

## Simplification

There are some differences between what data types the formats can represent: E.g., JSON can only represent booleans, numbers, strings, null, lists (arrays) and maps (objects), TOML additionally dates and times, while YAML and Pickle can theoretically represent any serializable type. config-formats will usually return whatever it can read and ask the target format to represent this, and the target format will try to convert the data to something it understands. Sometimes it is useful to _force_ simplification, e.g., in order to get rid of specific types when writing YAML. This can be triggered using `--simplify` or `-s`.
