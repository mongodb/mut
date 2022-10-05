from bson import decode_all
from json import loads
from pathlib import Path
from mut.index.SnootyManifest import ManifestEntry, Document, generate_manifest


ROOT_PATH = Path("../test_data_index/documents")


def setup_doc(root_path: Path, file_path: str) -> ManifestEntry:
    data = decode_all(root_path.joinpath(Path(file_path)).read_bytes())
    document = Document(data).export()
    assert document is not None
    return document


def test_findParagraphs() -> None:
    document = setup_doc(ROOT_PATH, "introduction.bson")
    expected = "MongoDB 6.0 release candidates are not yet available.\nThis version of the manual is for an upcoming release and is\ncurrently a work in progress. A record in MongoDB is a document, which is a data structure composed\nof field and value pairs. MongoDB documents are similar to JSON\nobjects. The values of fields may include other documents, arrays,\nand arrays of documents. The advantages of using documents are: Documents correspond to native data types in many programming\nlanguages. Embedded documents and arrays reduce need for expensive joins. Dynamic schema supports fluent polymorphism. MongoDB stores documents in  collections .\nCollections are analogous to tables in relational databases. In addition to collections, MongoDB supports: Read-only  Views  (Starting in MongoDB 3.4) On-Demand Materialized Views  (Starting in MongoDB 4.2). MongoDB provides high performance data persistence. In particular, Support for embedded data models reduces I/O activity on database\nsystem. Indexes support faster queries and can include keys from embedded\ndocuments and arrays. The MongoDB Query API supports  read and write\noperations (CRUD)  as well as: Data Aggregation Text Search  and  Geospatial Queries . SQL to MongoDB Mapping Chart SQL to Aggregation Mapping Chart Learn about the latest query language features with the  MongoDB\nQuery Language: What's New \npresentation from  MongoDB.live 2020 . MongoDB's replication facility, called  replica set , provides: A  replica set  is a group of\nMongoDB servers that maintain the same data set, providing redundancy\nand increasing data availability. automatic  failover data redundancy. MongoDB provides horizontal scalability as part of its  core \nfunctionality: Sharding  distributes data across a\ncluster of machines. Starting in 3.4, MongoDB supports creating  zones  of data based on the  shard key . In a\nbalanced cluster, MongoDB directs reads and writes covered by a zone\nonly to those shards inside the zone. See the  Zones \nmanual page for more information. MongoDB supports  multiple storage engines : In addition, MongoDB provides pluggable storage engine API that allows\nthird parties to develop storage engines for MongoDB. WiredTiger Storage Engine  (including support for\n Encryption at Rest ) In-Memory Storage Engine ."
    assert document["paragraphs"] == expected


def test_findHeadings() -> None:
    # Test h1 but no other headings
    document = setup_doc(ROOT_PATH, "code-example.bson")
    assert document["title"] == "Code Examples"
    assert document["headings"] == []

    # Test regular page format
    document = setup_doc(ROOT_PATH, "introduction.bson")
    expected_title = "Introduction to MongoDB"
    expected_headings = [
        "Document Database",
        "Collections/Views/On-Demand Materialized Views",
        "Key Features",
        "High Performance",
        "Query API",
        "High Availability",
        "Horizontal Scalability",
        "Support for Multiple Storage Engines",
    ]
    assert document["title"] == expected_title
    assert document["headings"] == expected_headings

    # Test headings with literals in them
    document = setup_doc(ROOT_PATH, "core/2dsphere.bson")
    assert document["title"] == "2dsphere Indexes"
    expected_headings = [
        "Overview",
        "Versions",
        "sparse Property",
        "Additional GeoJSON Objects",
        "Considerations",
        "geoNear and $geoNear Restrictions",
        "Shard Key Restrictions",
        "2dsphere Indexed Field Restrictions",
        "Limited Number of Index Keys",
        "Create a 2dsphere Index",
        "Create a 2dsphere Index",
        "Create a Compound Index with 2dsphere Index Key",
    ]
    assert document["headings"] == expected_headings


def test_derivePreview() -> None:
    # Test standard preview generation.
    document = setup_doc(ROOT_PATH, "core/2dsphere.bson")
    assert (
        document["preview"]
        == "A  2dsphere  index supports queries that calculate geometries on an\nearth-like sphere.  2dsphere  index supports all MongoDB geospatial\nqueries: queries for inclusion, intersection and proximity.\nFor more information on geospatial queries, see\n Geospatial Queries ."
    )

    # Test that pages that start with an admonition don't use the admonition
    # as the preview content.
    document = setup_doc(ROOT_PATH, "introduction.bson")
    assert (
        document["preview"]
        == "A record in MongoDB is a document, which is a data structure composed\nof field and value pairs. MongoDB documents are similar to JSON\nobjects. The values of fields may include other documents, arrays,\nand arrays of documents."
    )

    # Test page that starts with code reference declaration

    document = setup_doc(ROOT_PATH, "query/exists.bson")
    assert(
        document["preview"]
        == "Syntax :  { field: { $exists: <boolean> } }"
    )


    # Test that page with no paragraphs has no preview
    document = setup_doc(ROOT_PATH, "no-paragraphs.bson")
    assert document["preview"] == None

    # Test retrieving preview from metadata.
    document = setup_doc(ROOT_PATH, "has-meta-description.bson")
    assert (
        document["preview"]
        == "Cluster-to-Cluster Sync provides continuous data synchronization or a one-time data migration between two MongoDB clusters in the same or hybrid environments."
    )


def test_noIndex() -> None:
    # Test no headings at all
    document = setup_doc(ROOT_PATH, "no-title.bson")
    assert document == None

    # Test :robots: None in meta
    document = setup_doc(ROOT_PATH, "no-robots.bson")
    assert document == None


def test_findCode() -> None:
    # Test code from regular code block, IO Code block
    document = setup_doc(ROOT_PATH, "code-example.bson")
    expected = [
        {"lang": "python", "value": "a = 1\nb = 2\nprint(a)\nprint(b)"},
        {"lang": "python", "value": "b = 1\nc = 2\nprint(c)\nprint(b)"},
        {"lang": None, "value": "2\n1"},
    ]
    assert document["code"] == expected


def test_generate_manifest() -> None:
    # Test standard generation with two unindexable documents out of four
    ast_source = [
        ROOT_PATH.joinpath(Path("code-example.bson")),
        ROOT_PATH.joinpath(Path("introduction.bson")),
        ROOT_PATH.joinpath(Path("no-robots.bson")),
        ROOT_PATH.joinpath(Path("no-title.bson")),
    ]
    url = "www.mongodb.com/docs/test"
    includeInGlobalSearch = False

    manifest = loads(generate_manifest(ast_source, url, includeInGlobalSearch).export())
    assert len(manifest["documents"]) == 2
