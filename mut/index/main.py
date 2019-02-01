'''
Usage:
    mut-index <root> -o <output> -u <url> [-g -s --exclude <paths> --aliases <aliases>]
    mut-index upload [-b <bucket> -p <prefix>] <root> -o <output> -u <url>
                     [-g -s --exclude <paths> --aliases <aliases>]

    -h, --help             List CLI prototype, arguments, and options.
    <root>                 Path to the directory containing html files.
    -o, --output <output>  File name for the output manifest json. (e.g. manual-v3.2.json)
    --aliases <aliases>    Comma-delimited list of alternative manifest names.
                           (e.g. manual-v3.2) [default: ]
    --exclude <paths>      A comma-separated list of path prefixes to ignore. [default: ]
    -u, --url <url>        Base url of the property.
    -g, --global           Includes the manifest when searching all properties.
    -s, --show-progress    Shows a progress bar and other information via stdout.

    -b, --bucket <bucket>  Name of the s3 bucket to upload the index manifest to.
                           [default: docs-mongodb-org-prod]
    -p, --prefix <prefix>  Name of the s3 prefix to attached to the manifest.
                           [default: search-indexes]
'''
from docopt import docopt
from mut.index.Manifest import generate_manifest
from mut.index.s3upload import upload_manifest_to_s3
from mut.index.MarianActions import refresh_marian
from mut.index.utils.IntroMessage import print_intro_message


def main() -> None:
    '''Generate index files.'''
    options = docopt(__doc__)
    root = options['<root>']
    exclude = [path.strip() for path in options['--exclude'].split(',') if path]
    output = options['--output']
    aliases = [alias.strip() for alias in options['--aliases'].split(',') if alias.strip()]
    url = options['--url']
    globally = options['--global']
    show_progress = options['--show-progress']

    print_intro_message(root, exclude, output, aliases, url, globally)
    manifest = generate_manifest(url, aliases, root, exclude, globally, show_progress)
    if options['upload']:
        bucket = options['--bucket']
        prefix = options['--prefix']

        upload_manifest_to_s3(bucket, prefix, output, manifest)
        refresh_marian()
    else:
        with open('./' + output, 'w') as file:
            file.write(manifest)


if __name__ == "__main__":
    main()
