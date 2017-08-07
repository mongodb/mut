'''
Usage:
    mut-index <root> -o <output> -u <url> [-g -s]
    mut-index upload [-b <bucket> -p <prefix> --no-backup] <root> -o <output> -u <url> [-g -s]

    -h, --help             List CLI prototype, arguments, and options.
    <root>                 Path to the directory containing html files.
    -o, --output <output>  File name for the output manifest json. (e.g. manual-v3.2.json)
    -u, --url <url>        Base url of the property.
    -g, --global           Includes the manifest when searching all properties.
    -s, --show-progress    Shows a progress bar and other information via stdout.

    -b, --bucket <bucket>  Name of the s3 bucket to upload the index manifest to. [default: docs-mongodb-org-prod]
    -p, --prefix <prefix>  Name of the s3 prefix to attached to the manifest. [default: search-indexes]
    --no-backup            Disables automatic backup and restore of previous manifest versions.
'''
from docopt import docopt
from mut.index.Manifest import generate_manifest
from mut.index.s3upload import upload_manifest_to_s3
from mut.index.MarianActions import refresh_marian, FailedRefreshError
from mut.index.utils.IntroMessage import print_intro_message


def main() -> None:
    '''Generate index files.'''
    options = docopt(__doc__)
    root = options['<root>']
    output = options['--output']
    url = options['--url']
    globally = options['--global']
    show_progress = options['--show-progress']

    print_intro_message(root, output, url, globally)
    manifest = generate_manifest(url, root, globally, show_progress)
    if options['upload']:
        bucket = options['--bucket']
        prefix = options['--prefix']
        do_backup = not options['--no-backup']

        backup = upload_manifest_to_s3(bucket, prefix, output,
                                       manifest, do_backup)
        try:
            refresh_marian()
            print('\nAll according to plan!')
        except FailedRefreshError:
            if backup and do_backup:
                backup.restore()
    else:
        with open('./' + output, 'w') as file:
            file.write(manifest)


if __name__ == "__main__":
    main()
