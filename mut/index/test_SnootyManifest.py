from bson import decode_all
import pytest

from pathlib import Path

from .SnootyManifest import Document


ROOT_PATH = Path("test_bson_index")



def test_findParagraphs() -> None:
    path = ROOT_PATH.joinpath(Path("introduction.bson"))
    with open(path, 'rb') as f:
        data = decode_all(f.read())
        document = Document(data).export()
    expected = "MongoDB 6.0 release candidates are not yet available.\nThis version of the manual is for an upcoming release and is\ncurrently a work in progress.A record in MongoDB is a document, which is a data structure composed\nof field and value pairs. MongoDB documents are similar to JSON\nobjects. The values of fields may include other documents, arrays,\nand arrays of documents.The advantages of using documents are:Documents correspond to native data types in many programming\nlanguages.Embedded documents and arrays reduce need for expensive joins.Dynamic schema supports fluent polymorphism.MongoDB stores documents in collections.\nCollections are analogous to tables in relational databases.In addition to collections, MongoDB supports:Read-only Views (Starting in MongoDB 3.4)On-Demand Materialized Views (Starting in MongoDB 4.2).MongoDB provides high performance data persistence. In particular,Support for embedded data models reduces I/O activity on database\nsystem.Indexes support faster queries and can include keys from embedded\ndocuments and arrays.The MongoDB Query API supports read and write\noperations (CRUD) as well as:Data AggregationText Search and Geospatial Queries.SQL to MongoDB Mapping ChartSQL to Aggregation Mapping ChartLearn about the latest query language features with the MongoDB\nQuery Language: What's New\npresentation from MongoDB.live 2020.MongoDB's replication facility, called replica set, provides:A replica set is a group of\nMongoDB servers that maintain the same data set, providing redundancy\nand increasing data availability.automatic failoverdata redundancy.MongoDB provides horizontal scalability as part of its core\nfunctionality:Sharding distributes data across a\ncluster of machines.Starting in 3.4, MongoDB supports creating zones of data based on the shard key. In a\nbalanced cluster, MongoDB directs reads and writes covered by a zone\nonly to those shards inside the zone. See the Zones\nmanual page for more information.MongoDB supports multiple storage engines:In addition, MongoDB provides pluggable storage engine API that allows\nthird parties to develop storage engines for MongoDB.WiredTiger Storage Engine (including support for\nEncryption at Rest)In-Memory Storage Engine."
    assert document.paragraphs == expected
