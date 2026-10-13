# Libgen Calibre Store Plugin

This is a plugin for [Calibre](https://calibre-ebook.com/) which allows you to search libgen for books using Calibre's search for e-books feature

## Installation

- Download the zip file from the [Releases](https://github.com/poochinski9/libgen-calibre-store-plugin/releases) page
- Open Calibre
- Go to **Preferences -> Plugins -> Load Plugin from File** and select the zip file you downloaded.
- Restart Calibre
- Make sure the store is enabled under **Get Books -> Choose Stores**

## Releases

Release tags must match the version in `__init__.py`. Attach the matching `libgen-plugin-<version>.zip` to the GitHub Release.

## Tips

Calibre defaults to a maximum of 10 results returned at a time. You can change this maximum at **Get Books -> Configure -> Configure Search -> Maximum number of results...**

For better results and to get the format you are looking for, narrow down your search by title and author as much as possible.

## Choosing a mirror

Open **Preferences -> Plugins**, select **Library Genesis** under **Store plugins**, and click **Customize plugin**. The **Mirror** dropdown lets you choose a specific mirror or automatically select the first working JSON API, then fall back to a legacy homepage. After changing mirrors, search again; existing results retain their original book links.

Version 1.6.0 supports two frontends:

- Legacy HTML tables: `libgen.bz`, `libgen.vg`, `libgen.gl`, and `libgen.la`.
- JSON API frontend: `libgen.me`, `libgen.net`, `libgen.xyz`, `libgen.pw`, and `randombook.org`.

The JSON frontend supports search pagination and resolves its download landing pages into explicit file endpoints. If link resolution fails, the book page remains available for opening in a browser. HTTP 403/500 errors from the final file server can still prevent a download after Calibre receives the URL.

JSON frontend results show year and language. File sizes are omitted because the API's size units have not been independently verified.


## Advanced Search Mode (Google Mode)

Version 1.4.1 and greater supports Google mode.  Use the "title" field in calibre for this.

These operators apply to the legacy HTML table frontend. The JSON frontend receives the query as entered and uses its own search behavior.

For example, to search only `epub` format, type `Some book ext:epub`

Here is the full guide from libgen.gs. 

For more precise searches, use these operators:

- **Quotes** (`""`): Search for exact phrases as written in the database
- **Mask** (`*`): Search by part of a word (minimum 3 characters)
- **Excluding words** (`-`): Omit records containing specific words

#### Example
`"Physics and Chemistry" Basi* -technology`

This searches for:
- The exact phrase "Physics and Chemistry"
- Words starting with "Basi"
- Without the word "technology"

### Field-Specific Searches
Search specific fields using: `field_name:value`

### Additional Fields

#### For Files Tab
- `md5`
- `tth`
- `sha1`
- `sha256`
- `crc32`
- `edonkey`
- `doi`

#### View Modes
- `mode:last` - Last added entries (for a given object - series, authors, editions, etc.)
- `fmode:last` - Last added files (for the given repository)

#### For "Editions" and "Files" Objects
- `issuevolume` - Periodical volume
- `issuesid` - Serial ID of the periodical
- `issuenumber` - Number within the volume
- `issuetnumber` - Gross number of the periodical
- `issueynumber` - Intra-annual issue
- `year` - Year
- `publisherid` - Publisher ID
- `authorid` - Author's ID
- `lang` - Three-letter language code (ISO 639)
- `fsize` - Filesize in MBytes (supports: `fsize>10`, `fsize<20`, `fsize=15`)
- `ext` - File extension

#### For "Series" Object
- `comtopicid` - Classifier ID for comics
- `smtopicid` - Classifier ID for scientific journals
- `magtopicid` - Classifier ID for magazines
- `issn` - ISSN
