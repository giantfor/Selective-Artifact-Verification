// SPDX-License-Identifier: MIT
pragma solidity 0.8.30;

/// Versioned, immutable commitments. This is an authorization contract,
/// not a consensus implementation or a guarantee of clinical correctness.
contract CommitmentRegistry {
    address public immutable owner;
    struct Commitment {
        bytes32 datasetHash;
        bytes32 modelHash;
        bytes32 schemaHash;
        bytes32 parentDigest;
        uint256 recordCount;
        bool exists;
    }
    mapping(bytes32 => Commitment) private versions;
    mapping(bytes32 => mapping(uint256 => bytes32)) public batchHashes;
    event Registered(bytes32 indexed version, bytes32 datasetHash, bytes32 modelHash,
        bytes32 schemaHash, bytes32 parentDigest, uint256 recordCount);
    event BatchRegistered(bytes32 indexed version, uint256 indexed batchIndex,
        bytes32 payloadHash, uint256 recordCount);
    constructor() { owner = msg.sender; }
    modifier onlyOwner() { require(msg.sender == owner, "unauthorized"); _; }
    function register(bytes32 version, bytes32 datasetHash, bytes32 modelHash,
        bytes32 schemaHash, bytes32 parentDigest, uint256 recordCount) external onlyOwner {
        require(!versions[version].exists, "immutable version");
        require(version != bytes32(0) && datasetHash != bytes32(0)
            && modelHash != bytes32(0) && schemaHash != bytes32(0) && recordCount > 0, "invalid commitment");
        versions[version] = Commitment(datasetHash,modelHash,schemaHash,parentDigest,recordCount,true);
        emit Registered(version,datasetHash,modelHash,schemaHash,parentDigest,recordCount);
    }
    function get(bytes32 version) external view returns (Commitment memory) { return versions[version]; }
    function registerBatch(bytes32 version, uint256 batchIndex, bytes32 payloadHash,
        uint256 recordCount) external onlyOwner {
        require(versions[version].exists, "unknown version");
        require(batchHashes[version][batchIndex] == bytes32(0), "immutable batch");
        require(payloadHash != bytes32(0) && recordCount > 0, "invalid batch");
        batchHashes[version][batchIndex] = payloadHash;
        emit BatchRegistered(version,batchIndex,payloadHash,recordCount);
    }
}
