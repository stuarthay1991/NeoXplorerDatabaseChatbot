from langchain_core.tools import tool
from typing import Literal
import json

pancancer_table_dict = {
    "supersig": [["COLUMN NAME: cancer_name", "COLUMN DESCRIPTION: The cancer name this event belongs to."],
                ["COLUMN NAME: signature_name", "COLUMN DESCRIPTION: The subtype this event belongs to."],
                ["COLUMN NAME: uid", "COLUMN DESCRIPTION: The unique identifier for this event."],
                ["COLUMN NAME: firstjunc", "COLUMN DESCRIPTION: The first junction in this event."],
                ["COLUMN NAME: event_direction", "COLUMN DESCRIPTION: The direction of the event."],
                ["COLUMN NAME: eventannotation", "COLUMN DESCRIPTION: The type of event this is."]
    ],
    "neo_cluster_synonym": [["COLUMN NAME: oncobrowserlookup", "COLUMN DESCRIPTION: The universally understood name of the subtype, this can be matched across the database."],
                ["COLUMN NAME: clusterid", "COLUMN DESCRIPTION: Version of the subtype that is easier to read"],
                ["COLUMN NAME: synonym", "COLUMN DESCRIPTION: The list of the synonyms for the subtype, separated by a | character for each"]
    ],
    "survival": [["COLUMN NAME: cancer", "COLUMN DESCRIPTION: The cancer name this event belongs to."],
            ["COLUMN NAME: uid", "COLUMN DESCRIPTION: The unique identifier for this event."],
            ["COLUMN NAME: eventannotation", "COLUMN DESCRIPTION: The type of event this is."],
            ["COLUMN NAME: zscore", "COLUMN DESCRIPTION: The zscore."],
            ["COLUMN NAME: lrtpvalue", "COLUMN DESCRIPTION: Likelihood Ratio Test p-value. Low values indicate suvival."],
            ["COLUMN NAME: mlog10lrtp", "COLUMN DESCRIPTION: Modified lrtp."]
    ],
    "hs_exon": [["COLUMN NAME: gene", "COLUMN DESCRIPTION: The gene name this exon belongs to."],
            ["COLUMN NAME: exon_id", "COLUMN DESCRIPTION: The name of the exon."],
            ["COLUMN NAME: chromosome", "COLUMN DESCRIPTION: The name of the chromosome."],
            ["COLUMN NAME: exon_region_start_s_", "COLUMN DESCRIPTION: Genomic coordinates where the exon starts."],
            ["COLUMN NAME: exon_region_stop_s_", "COLUMN DESCRIPTION: Genomic coordinates where the exon ends."],
            ["COLUMN NAME: ens_exon_ids", "COLUMN DESCRIPTION: Other isoforms for this exon"]
    ],
    "hs_junc": [["COLUMN NAME: gene", "COLUMN DESCRIPTION: The gene name this junction belongs to."],
            ["COLUMN NAME: exon_id", "COLUMN DESCRIPTION: The name of the junction."],
            ["COLUMN NAME: chromosome", "COLUMN DESCRIPTION: The name of the chromosome."],
            ["COLUMN NAME: exon_region_start_s_", "COLUMN DESCRIPTION: Genomic coordinates where the junction starts."],
            ["COLUMN NAME: exon_region_stop_s_", "COLUMN DESCRIPTION: Genomic coordinates where the junction ends."],
            ["COLUMN NAME: ens_exon_ids", "COLUMN DESCRIPTION: Other isoforms this junction is involved with"]
    ],
    "hs_transcript_annot": [["COLUMN NAME: ensembl_gene_id", "COLUMN DESCRIPTION: The ensembl gene id this isoform belongs to."],
            ["COLUMN NAME: chromosome", "COLUMN DESCRIPTION: The chromosome this isoform is on"],
            ["COLUMN NAME: exon_start__bp_", "COLUMN DESCRIPTION: Where this isoform begins"],
            ["COLUMN NAME: exon_end__bp_", "COLUMN DESCRIPTION: Where this isoform ends"],
            ["COLUMN NAME: ensembl_exon_id", "COLUMN DESCRIPTION: ensembl exon id for this transcript"],
            ["COLUMN NAME: ensembl_transcript_id", "COLUMN DESCRIPTION: ensembl transcript id for this transcript"]
    ]
}

example_questions = {
    "supersig": [],
    "neo_cluster_synonym": [],
    "survival": [],
    "hs_exon": [],
    "hs_junc": [],
    "hs_transcript_annot": []
}

@tool
async def query_neoxUniversal(
    table_name: Literal["supersig", "neo_cluster_synonym", "survival", "hs_exon", "hs_junc", "hs_transcript_annot"]
) -> str:
    """ 
    USE WHEN: The user is asking for database wide metrics. 
    For example, 'How many cancers are there?', 'How many subtypes are in the database total?', 'How many splicing events are in the database?'

    Complex example question: what clusters have the synonym c15? You will search for that term using a LIKE operative for the synonym in column 'synonym' in table neo_cluster_synonym and return the respective clusterid values.

    HOW TO USE: Decide the relevant table and columns based on the user's prompt. Pick from 'supersig', 'neo_cluster_antonym', or 'survival' based on what the user is asking. HOW TO USE: Decide the relevant table and columns based on the user's prompt. Then decide the USE value of the columns that are selected, can be one of two values (either RETURN or FILTER. RETURN is the column selected, while FILTER is a column filtered on using where or like statements.) Then decide the QUERYTYPE (can be one or more of these values, COUNT, DISTINCT, or FILTERED)
    
    table_name: Table type (
    supersig=(contains all subtypes for all cancers and their respective events (it lists their uids)), 
    neo_cluster_synonym=(contains all subtypes for all cancers and synonyms for the subtype), 
    survival=(Contains information for survival statistics)),
    hs_exon=(Contains all exons in the database)),
    hs_junc=(Contains all junctions in the database)),
    hs_transcript_annot=(Contains all transcripts in the database)
    """
    # Get column information for the selected table
    columns = pancancer_table_dict.get(table_name, [])

    # Build JSON output
    column_list = []
    for col in columns:
        col_name = col[0].replace("COLUMN NAME: ", "") if col[0].startswith("COLUMN NAME: ") else col[0]
        col_desc = col[1].replace("COLUMN DESCRIPTION: ", "") if col[1].startswith("COLUMN DESCRIPTION: ") else col[1]
        column_list.append({"column_name": col_name, "description": col_desc})

    result = {"table_name": table_name, "columns": column_list}
    print("resultName", result)
    return json.dumps(result, indent=2)