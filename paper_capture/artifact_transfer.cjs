'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { DefaultArtifactClient } = require('@actions/artifact');

const client = new DefaultArtifactClient();
const runId = process.env.GITHUB_RUN_ID;
const attempt = process.env.GITHUB_RUN_ATTEMPT;
const partsRoot = path.resolve('capture-parts');
const stageRoot = path.resolve('stage-batch');
const retentionDays = 90;
const maxFilesPerBatch = Number(process.env.PAPER_MAX_FILES_PER_BATCH || 10);
const manifestFileNames = ['manifest.json', 'parts-manifest.json'];

function walkFiles(root) {
  const found = [];
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const full = path.join(root, entry.name);
    if (entry.isDirectory()) found.push(...walkFiles(full));
    else if (entry.isFile()) found.push(full);
  }
  return found;
}

function byBasename(root, name) {
  const found = walkFiles(root).filter((file) => path.basename(file) === name);
  if (found.length !== 1) {
    throw new Error(`expected exactly one ${name} under ${root}; found ${found.length}`);
  }
  return found[0];
}

function artifactOptions() {
  return { retentionDays, compressionLevel: 0 };
}

async function stage() {
  const manifestPath = path.join(partsRoot, 'parts-manifest.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const batchDirs = fs.readdirSync(path.join(partsRoot, 'staging'), { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && /^batch-\d{3}$/.test(entry.name))
    .map((entry) => path.join(partsRoot, 'staging', entry.name))
    .sort();

  if (!manifest.parts.length || !batchDirs.length || batchDirs.length > 10) {
    throw new Error(`invalid staging plan: parts=${manifest.parts.length}, batches=${batchDirs.length}`);
  }

  for (let batch = 0; batch < batchDirs.length; batch += 1) {
    const files = walkFiles(batchDirs[batch]);
    if (!files.length || files.length > maxFilesPerBatch) {
      throw new Error(`batch ${batch} has ${files.length} files; expected 1..${maxFilesPerBatch}`);
    }
    const name = `paper-market-stage-${runId}-${attempt}-batch-${batch}`;
    const result = await client.uploadArtifact(name, files, artifactOptions());
    console.log(`PAPER_STAGE_UPLOADED batch=${batch} files=${files.length} bytes=${result.size}`);
  }

  fs.appendFileSync(process.env.GITHUB_OUTPUT, `upload_batches=${JSON.stringify(batchDirs.map((_, i) => i))}\n`);
  console.log(`PAPER_STAGE_COMPLETE parts=${manifest.parts.length} batches=${batchDirs.length}`);
}

function partBatch(index) {
  const firstBatchPartCapacity = maxFilesPerBatch - manifestFileNames.length;
  if (firstBatchPartCapacity <= 0) {
    throw new Error(
      `batch limit ${maxFilesPerBatch} leaves no room after ${manifestFileNames.length} manifest files`,
    );
  }
  if (index < firstBatchPartCapacity) return 0;
  return 1 + Math.floor((index - firstBatchPartCapacity) / maxFilesPerBatch);
}

async function publish() {
  const batch = Number(process.env.BATCH_INDEX);
  if (!Number.isInteger(batch) || batch < 0) throw new Error('invalid BATCH_INDEX');
  const manifestPath = path.join(stageRoot, 'parts-manifest.json');
  const manifestExists = walkFiles(stageRoot).some((file) => path.basename(file) === 'parts-manifest.json');
  let manifest = null;
  if (manifestExists) manifest = JSON.parse(fs.readFileSync(byBasename(stageRoot, 'parts-manifest.json'), 'utf8'));

  const expectedParts = manifest
    ? manifest.parts.filter((part) => partBatch(part.index) === batch)
    : walkFiles(stageRoot)
        .map((file) => path.basename(file).match(/^events\.jsonl\.gz\.part(\d{3})$/))
        .filter(Boolean)
        .map((match) => ({ index: Number(match[1]), name: `events.jsonl.gz.part${match[1]}` }))
        .filter((part) => partBatch(part.index) === batch);

  if (!expectedParts.length) throw new Error(`no parts assigned to batch ${batch}`);
  let uploaded = 0;
  for (const part of expectedParts) {
    const file = byBasename(stageRoot, part.name);
    const name = `paper-market-tape-${runId}-${attempt}-part-${String(part.index).padStart(3, '0')}`;
    const result = await client.uploadArtifact(name, [file], artifactOptions());
    uploaded += 1;
    console.log(`PAPER_PART_UPLOADED index=${part.index} artifact_id=${result.id} bytes=${result.size}`);
  }

  if (batch === 0) {
    const manifestFiles = walkFiles(stageRoot).filter((file) =>
      ['manifest.json', 'parts-manifest.json'].includes(path.basename(file)));
    if (manifestFiles.length !== 2) throw new Error(`batch 0 must contain both manifests; found ${manifestFiles.length}`);
    const result = await client.uploadArtifact(
      `paper-market-tape-${runId}-${attempt}-manifest`,
      manifestFiles,
      artifactOptions(),
    );
    uploaded += 1;
    console.log(`PAPER_MANIFEST_UPLOADED artifact_id=${result.id} bytes=${result.size}`);
  }

  if (uploaded > 10) throw new Error(`batch ${batch} attempted to exceed the 10-artifact job limit`);
  console.log(`PAPER_PUBLISH_BATCH_COMPLETE batch=${batch} uploaded_artifacts=${uploaded} parts=${expectedParts.length}`);
}

(async () => {
  if (!runId || !attempt) throw new Error('GitHub run identity is missing');
  if (process.argv[2] === 'stage') await stage();
  else if (process.argv[2] === 'publish') await publish();
  else throw new Error('usage: artifact_transfer.cjs stage|publish');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
