"""
Usage:
    mut-index <root> -o <output> -u <url> [-g -s]
    mut-index upload [-b <bucket> -p <prefix>] <root> -o <output> -u <url>
                     [-g -s]

    -h, --help             List CLI prototype, arguments, and options.
    <root>                 Path to the directory containing html files.
    -o, --output <output>  File name for the output manifest json. (e.g. manual-v3.2.json)
    -u, --url <url>        Base url of the property.
    -g, --global           Includes the manifest when searching all properties.

    -b, --bucket <bucket>  Name of the s3 bucket to upload the index manifest to.
    -p, --prefix <prefix>  Name of the s3 prefix to attached to the manifest.
                           [default: search-indexes]
"""
from docopt import docopt
from mut.index.SnootyManifest import generate_manifest, get_ast_list
from mut.index.s3upload import upload_manifest_to_s3
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Generate index files."""
    print("Start time: {}".format(datetime.now()))
    options = docopt(__doc__)
    root = options["<root>"]
    output = options["--output"]
    url = options["--url"]
    globally = options["--global"]
    logger.info("Getting AST list: {}".format(datetime.now()))
    ast_source = get_ast_list(root)
    logger.info("staring manifest generation: {}".format(datetime.now()))
    manifest = generate_manifest(ast_source, url, globally).export()

    if options["upload"]:
        bucket = options["--bucket"]
        prefix = options["--prefix"]

        upload_manifest_to_s3(bucket, prefix, output, manifest)
    else:
        with open("./" + output, "w") as file:
            file.write(manifest)
    print("Finish time: {}".format(datetime.now()))


if __name__ == "__main__":
    main()
