# Libgen Calibre Store Plugin

This is a plugin for [Calibre](https://calibre-ebook.com/) which allows you to search libgen for books using Calibre's search for e-books feature

## Installation

- Download the zip file from the [Releases](https://github.com/poochinski9/libgen-calibre-store-plugin/releases) page
- Open Calibre
- Go to **Preferences -> Plugins -> Load Plugin from File** and select the zip file you downloaded.
- Restart Calibre
- Make sure the store is enabled under **Get Books -> Choose Stores**

## Tips

Calibre defaults to a maximum of 10 results returned at a time. You can change this maximum at **Get Books -> Configure -> Configure Search -> Maximum number of results...**

For better results and to get the format you are looking for, narrow down your search by title and author as much as possible.


## Advanced Search Mode (Google Mode)

Version 1.4.1 and greater supports Google mode.  Use the "title" field in calibre for this.

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
