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
* `--simplify`, `-s` – force conversion to a limited set of data types.
* `-q` _jsonpath_, `--query` _jsonpath_ – Perform a JSONpath query in the input data
* `-p` _prefix_, `--prefix` _prefix_ – Nest result in one or more tables.
* `--pretty` / `--no-pretty` – Pretty-print the output. See below.
* `-v`, `--verbose`; `-vv`, `--debug` – increase informational output on stderr.

## Simplification and data conversion

The various data formats supported by the tool differ in the details of the values they support. E.g., YAML can represent almost any data type, JSON allows arbitrarily nested mappings (objects) and lists (arrays) as well as strings, numbers, boolean and null values, TOML additionally allows dates and times, but forbids `null` values, environment variables do not really allow nested structures, but sometimes use lists of simple values by seperating them with `:`.

config-formats features a type conversion component that is able to recursively process the structure that has been read and apply configurable rules to convert data types that the target format cannot handle or to _upconvert_ representations of data types that are not directly supported in the source format. In the current implementation, some file formats apply a specialized conversion after loading or before saving. Additionally, a generic conversion (called _simplification_) can be triggered between the steps using the `-s` switch. This default conversion produces JSON-compatible data.

Use `config-formats formats` to see which conversions are used for each format.

Here are the currently available options. The default of all boolean options is false/off.

| Option                      | Explanation                                                                                                 |
|-----------------------------+-------------------------------------------------------------------------------------------------------------|
| allow_date                  | Retain date and time types in the data instead of converting them to ISO-8601 strings                       |
| parse_date                  | Try to parse strings as date or time                                                                        |
| parse_str                   | Try to "upconvert" strings to other simple types (bool, numbers, null)                                      |
| - special_tokens            | if parse_str is used, convert these strings (true,false,on,off,null) directly to specific non-string values |
| skip_null_values            | Remove key-value-pairs with a null value from mappings.                                                     |
| skip_null_keys              | Remove key-value-pairs with a null key from mappings.                                                       |
| force_string_keys           | Mapping keys are always converted to strings                                                                |
| parse_simple_lists          | should we try to parse strings into simple lists¹?                                                          |
| join_simple_lists           | should we convert a list of values that are all simple types to a string¹?                                  |
| simple_list_separator       | the separator for the simple lists, by default `;`                                                          |
| simple_list_final_separator | does a simple list always end with the separator? (E.g., in XDG desktop files)                              |
| simple_types                | (for simple lists, default: bool, int, float, str, NoneType)                                                |
| max_level                   | Levels deeper than this are serialized/parsed using max_level_format (default: off)                         |
| max_level_format            | Format for complex structures on level max_level (default: JSON)                                                            |

Environment and INI files do not really have a fully-featured array type, but they sometimes use string values that really are lists of items, separated using a separator like ':' or ';' (think `$PATH`). We call those lists _simple lists_ and can both parse and serialize them on demand. To avoid too many false positives, parsing only works for simple lists with at least three elements (otherwise, e.g., URLs might be split into `["http", "//github.com"]`). Joining lists to a string with a simple list requires each element to be a simple type, which will then be converted to a string first.

## Structure modifications

### Selecting Data using JSONpath

It is possible to select only specific data from the source by specifying a JSONpath query. E.g.,

```sh
config-formats --query project.scripts.~ pyproject.toml
```

will output a list of the script names defined py the given pyproject.toml file (it will parse the TOML file, run the JSONpath query `project.scripts.~` on it and serialize the result as YAML). If a query is given, everything that is _not_ selected by the query will be discarded.

### Nesting data in subtables

Using the `-p` / `--prefix` option, you can optionally nest _all_ incoming data into s subtable structure in the output. The _prefix_ argument is something that you would write between sqare brackets in a TOML file, i.e. it is a dotted string of key names. This can be used, e.g., to convert legacy configuration files to pyproject.toml tables, e.g.

```bash
config-formats -t toml -p tool.pixi pixi.toml >> pyproject.toml
config-formats -q pytest \ # step into the [pytest] section in the ini file
               -p tool.pytest.ini_options \ # put it into [tool.pytest.ini_options]
               pytest.ini >> pypproject.toml
```

### Workflow

The workflow is always

> parse → simplify¹ → query¹ → prefix¹ → serialize (→ syntax highlight)
>
> ¹ if enabled via option

independent of the order in which options are given.

## Exit codes

| 0 | everything went fine        |
| 1 | invalid command line etc.   |
| 2 | failed to read input file   |
| 3 | failed to write output file |

## Auto-detection

If the source format is neither specified using the `--from` option nor using the input file name’s suffix, the program tries to auto-detect the format. It does so by simply trying to parse the input using each of the formats in the order they are listed using `config-formats formats` and taking the first one that works without errors.
