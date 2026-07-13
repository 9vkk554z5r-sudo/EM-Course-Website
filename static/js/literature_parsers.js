(function () {
    function parseDoiText(text) {
        return String(text || '').split(/\n+/).map(function (line) {
            var doi = line.trim().replace(/^doi:\s*/i, '');
            return doi ? { doi: doi, title: 'DOI ' + doi, source: 'doi' } : null;
        }).filter(Boolean);
    }

    function fieldValue(block, name) {
        var re = new RegExp(name + '\\s*=\\s*[\\{"]([\\s\\S]*?)[\\}"]\\s*,?', 'i');
        var match = block.match(re);
        return match ? match[1].replace(/\s+/g, ' ').trim() : '';
    }

    function parseBibTeX(text) {
        var blocks = String(text || '').split(/@\w+\s*\{/).slice(1);
        return blocks.map(function (block) {
            return {
                title: fieldValue(block, 'title'),
                authors: fieldValue(block, 'author').replace(/\s+and\s+/gi, '; '),
                year: fieldValue(block, 'year'),
                doi: fieldValue(block, 'doi'),
                journal: fieldValue(block, 'journal') || fieldValue(block, 'booktitle'),
                abstract: fieldValue(block, 'abstract'),
                keywords: fieldValue(block, 'keywords'),
                source: 'bibtex',
            };
        }).filter(function (paper) { return paper.title || paper.doi; });
    }

    function parseRIS(text) {
        var records = String(text || '').split(/\nER\s*-\s*/i);
        return records.map(function (record) {
            var paper = { authors: [], keywords: [], source: 'ris' };
            record.split(/\r?\n/).forEach(function (line) {
                var match = line.match(/^([A-Z0-9]{2})\s*-\s*(.*)$/);
                if (!match) return;
                var tag = match[1];
                var value = match[2].trim();
                if (tag === 'TI' || tag === 'T1') paper.title = value;
                if (tag === 'AU' || tag === 'A1') paper.authors.push(value);
                if (tag === 'PY' || tag === 'Y1') paper.year = value;
                if (tag === 'DO') paper.doi = value;
                if (tag === 'JO' || tag === 'JF' || tag === 'T2') paper.journal = value;
                if (tag === 'AB' || tag === 'N2') paper.abstract = value;
                if (tag === 'KW') paper.keywords.push(value);
            });
            return paper;
        }).filter(function (paper) { return paper.title || paper.doi; });
    }

    function parseCsvRows(text) {
        var rows = [];
        var row = [];
        var cell = '';
        var quoted = false;
        var value = String(text || '');
        for (var i = 0; i < value.length; i += 1) {
            var ch = value[i];
            var next = value[i + 1];
            if (ch === '"' && quoted && next === '"') {
                cell += '"';
                i += 1;
            } else if (ch === '"') {
                quoted = !quoted;
            } else if (ch === ',' && !quoted) {
                row.push(cell);
                cell = '';
            } else if ((ch === '\n' || ch === '\r') && !quoted) {
                if (ch === '\r' && next === '\n') i += 1;
                row.push(cell);
                if (row.some(function (item) { return item.trim(); })) rows.push(row);
                row = [];
                cell = '';
            } else {
                cell += ch;
            }
        }
        row.push(cell);
        if (row.some(function (item) { return item.trim(); })) rows.push(row);
        return rows;
    }

    function parseCSV(text) {
        var rows = parseCsvRows(text);
        if (rows.length < 2) return [];
        var headers = rows[0].map(function (h) { return h.trim().toLowerCase(); });
        return rows.slice(1).map(function (row) {
            var item = {};
            headers.forEach(function (header, index) { item[header] = (row[index] || '').trim(); });
            return {
                title: item.title,
                authors: item.authors || item.author,
                year: item.year,
                doi: item.doi,
                journal: item.journal,
                abstract: item.abstract,
                keywords: item.keywords,
                citationCount: item.citationcount || item.citation_count || item.citations,
                source: 'csv',
            };
        }).filter(function (paper) { return paper.title || paper.doi; });
    }

    function samplePapers() {
        return [
            {
                title: 'High-resolution cryo-EM structures and single particle reconstruction workflows',
                authors: 'Yifan Cheng; Bridget Carragher; Clint Potter',
                year: 2022,
                doi: '10.1000/cryo-em-workflow',
                journal: 'Nature Methods',
                abstract: 'A practical overview of cryo-EM sample preparation, image acquisition, particle picking, 2D classification, 3D refinement, and validation.',
                keywords: 'cryo-EM; single particle analysis; RELION; cryoSPARC; reconstruction',
                citationCount: 420,
            },
            {
                title: 'Electron tomography for cellular structural biology',
                authors: 'Wanda Kukulski; John Briggs',
                year: 2021,
                doi: '10.1000/electron-tomography-cell',
                journal: 'Current Opinion in Structural Biology',
                abstract: 'Electron tomography reveals macromolecular organization in cells and connects cellular context with structural interpretation.',
                keywords: 'electron tomography; subtomogram averaging; cellular structural biology; cryo-ET',
                citationCount: 310,
            },
            {
                title: 'Deep learning approaches for particle picking in cryo-EM',
                authors: 'Thorsten Wagner; Sjors Scheres',
                year: 2020,
                doi: '10.1000/particle-picking-ai',
                journal: 'eLife',
                abstract: 'Machine learning methods improve particle picking and reduce manual bias in single particle cryo-EM workflows.',
                keywords: 'particle picking; deep learning; single particle analysis; preprocessing',
                citationCount: 260,
            },
            {
                title: 'Sample preparation strategies for vitrified biological specimens',
                authors: 'Robert Glaeser; Joachim Frank',
                year: 2019,
                doi: '10.1000/vitrification-sample-prep',
                journal: 'Journal of Structural Biology',
                abstract: 'Specimen quality, grid preparation, blotting, vitrification and contamination control shape downstream reconstruction quality.',
                keywords: 'sample preparation; vitrification; grids; contamination; cryo-EM',
                citationCount: 360,
            },
            {
                title: 'Validation and resolution assessment in cryo-EM maps',
                authors: 'Richard Henderson; Marin van Heel',
                year: 2018,
                doi: '10.1000/cryo-em-validation',
                journal: 'IUCrJ',
                abstract: 'Resolution, map validation, overfitting control, FSC and model-to-map agreement remain critical for interpretable cryo-EM structures.',
                keywords: 'validation; FSC; map resolution; reconstruction; model building',
                citationCount: 500,
            },
        ];
    }

    window.LiteratureParsers = {
        parseDoiText: parseDoiText,
        parseBibTeX: parseBibTeX,
        parseRIS: parseRIS,
        parseCSV: parseCSV,
        samplePapers: samplePapers,
    };
})();
