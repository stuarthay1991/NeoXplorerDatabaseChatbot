from langchain_core.tools import tool
from typing import Literal
import json

cancer_table_type_dict = {
    "_splice": [["COLUMN NAME: symbol", "COLUMN DESCRIPTION: The gene symbol associated with this splicing event"],
                ["COLUMN NAME: description", "COLUMN DESCRIPTION: Description of the splicing event"],
                ["COLUMN NAME: dpsi", "COLUMN DESCRIPTION: Differential Percentage Spliced In. A high value means the exon is included, whereas a low value means it is not included."],
                ["COLUMN NAME: uid", "COLUMN DESCRIPTION: Unique identifier for the splicing event. Count these to find the number of splicing events for this cancer. Contains the gene symbol, ENSEMBL Id, and the examined_junction  and background_major_junction."],
                ["COLUMN NAME: examined_junction", "COLUMN DESCRIPTION: Contains the ENSEMBL id and to the specific splice junction (exon-exon junction) that is being tested for differential splicing, novel usage, or expression levels in a particular sample or condition."],
                ["COLUMN NAME: eventannotation", "COLUMN DESCRIPTION: Describes event type. Can be one of the following (trans-splicing, alt-3, alt-5, cassette-exon, altPromoter, alt-C-term, intron-retention)"],
                ["COLUMN NAME: background_major_junction", "COLUMN DESCRIPTION: Contains the ENSEMBL id and the most highly expressed (dominant) splicing junction for a given splicing event within the same gene."],
                ["COLUMN NAME: altexons", "COLUMN DESCRIPTION: Other isoforms associated with this event"],
                ["COLUMN NAME: cluster_id", "COLUMN DESCRIPTION: cluster this splicing event belongs to"],
                ["COLUMN NAME: chromosome", "COLUMN DESCRIPTION: Chromosome this junction is on."],
                ["COLUMN NAME: coord1", "COLUMN DESCRIPTION: Start coordinate of the first junction."],
                ["COLUMN NAME: coord2", "COLUMN DESCRIPTION: End coordinate of the first junction."],
                ["COLUMN NAME: coord3", "COLUMN DESCRIPTION: Start coordinate of the second junction."],
                ["COLUMN NAME: coord4", "COLUMN DESCRIPTION: End coordinate of the second junction."],
                ["ANY COLUMN THAT STARTS WITH tcga_", "COLUMN DESCRIPTION: The column represents a patient and how significant a specific splicing event is for that patient."]
    ],
    "_signature": [["COLUMN NAME: uid", "COLUMN DESCRIPTION: This is the unique identifier of the splicing event"],
                ["ALL OTHER COLUMNS", "COLUMN DESCRIPTION: Every other column is a subtype of the cancer. A value of 1 signifies that splicing event is a part of the subtype, and value of 0 signifies it is not. If you want to find all subtypes for a given cancer, find the names of all columns in this table that are not named 'uid'"]
    ],
    "_meta": [["COLUMN NAME: uid", "COLUMN DESCRIPTION: Each value in this column is a patient that corresponds the columns that start with tcga_ in the _splice table"],
            ["COLUMN NAME: race", "COLUMN DESCRIPTION: Race of patient (can be these values: WHITE, BLACK OR AFRICAN AMERICAN, ASIAN, NA, UNK)"],
            ["COLUMN NAME: gender", "COLUMN DESCRIPTION: Gender of patient (can be these values: MALE, FEMALE, UNK)"],
            ["COLUMN NAME: tumor_stage", "COLUMN DESCRIPTION: Stage of patient's tumor (can be these values: Stage I, Stage II, Stage III, Stage IV, UNK)"],
            ["COLUMN NAME: bmi_status", "COLUMN DESCRIPTION: bmi index of the patient (can be these values: NA, Normal, Overweight, Underweight, Obese)"],
            ["ALL OTHER COLUMNS", "COLUMN DESCRIPTION: Every other column in this table signifies a category a patient is in, whether it is ethnicity, tumor location, or age."]
    ],
    "_fullsig": [["COLUMN NAME: signature_name", "COLUMN DESCRIPTION: Subtype this uid is associated with. To get all subtypes for a cancer, use a DISTINCT query for this column."],
                ["COLUMN NAME: coordinates", "COLUMN DESCRIPTION: Genomic coordinates associated with this event."],
                ["COLUMN NAME: dpsi", "COLUMN DESCRIPTION: Differential Percentage Spliced In. A high value means the exon is included, whereas a low value means it is not included."],
                ["COLUMN NAME: rawp", "COLUMN DESCRIPTION: (raw p-value) statistical significance of the event"],
                ["COLUMN NAME: event_direction", "COLUMN DESCRIPTION: Is one of two values (exclusion, inclusion)"],
                ["COLUMN NAME: eventannotation", "COLUMN DESCRIPTION: Describes event type. Can be one of the following (trans-splicing, alt-3, alt-5, cassette-exon, altPromoter, alt-C-term, intron-retention)"],
                ["COLUMN NAME: adjp", "COLUMN DESCRIPTION: (corrected p-value) corrects to combat false positives."],
                ["COLUMN NAME: uid", "COLUMN DESCRIPTION: Unique identifier for the splicing event. Contains the gene symbol, ENSEMBL Id, and the examined_junction  and background_major_junction."]
                ],
    "_fulldegene": [["COLUMN NAME: signature_name", "COLUMN DESCRIPTION: Subtype this event is associated with. To get all subtypes for a cancer, use a DISTINCT query for this column."],
                ["COLUMN NAME: geneid", "COLUMN DESCRIPTION: Ensembl ID this event is assocaited with"],
                ["COLUMN NAME: symbol", "COLUMN DESCRIPTION: The gene symbol associated with this splicing event"],
                ["COLUMN NAME: rawp", "COLUMN DESCRIPTION: (raw p-value) statistical significance of the event"],
                ["COLUMN NAME: adjp", "COLUMN DESCRIPTION: (corrected p-value) corrects to combat false positives."]
                ]
}

example_questions = {
    "_splice": [],
    "_signature": [],
    "_meta": [],
    "_fullsig": [],
    "_fulldegene": []
}

@tool
async def query_neoxCancerSpecific(
    cancer_prefix: Literal["blca", "brca", "cesc", "coad", "esca", "gbm", "hnsc", "kich", "kirc", "lgg", "lihc", "luad", "lusc", "ov", "paad", "pcpg", "prad", "read", "sarc", "skcm", "stad", "tgct", "thca", "ucec"],
    table_suffix: Literal["_splice", "_signature", "_meta", "_fullsig", "_fulldegene"]
) -> str:
    """ 
    USE WHEN: The user is asking about one or more specific cancers.

    CRITICAL: If the user mentions MULTIPLE cancers (e.g., "LUAD and BRCA", "BRCA, COAD, and LUAD"), you MUST call this tool MULTIPLE times - once for EACH cancer mentioned. For example, if asked about "LUAD and BRCA", call this tool twice: once with cancer_prefix="luad" and once with cancer_prefix="brca".

    HOW TO USE: Decide the relevant table and columns based on the user's prompt. Then decide the USE value of the columns that are selected, can be one of two values (either RETURN or FILTER. RETURN is the column selected, while FILTER is a column filtered on using where or like statements.) Then decide the QUERYTYPE (can be one or more of these values, COUNT, DISTINCT, or FILTERED)

    cancer_prefix: Cancer type codes (blca=bladder, brca=breast, coad=colon, luad=lung adenocarcinoma, etc.)
    table_suffix: Table type (
    _splice=(splicing events for all patients with this cancer. Also contains genomic coordinates and the gene symbol for said splicing event. columns starting with tcga are patient specific. ), 
    _signature=(first column is the uid for a specific event, all other columns contain the subtypes associated with the cancer. The table is used to determine whether or not a splicing event is part of a particular subtype.), 
    _meta=(Contains information for individual patients (think ethnicity, age, tumor location)), 
    _fullsig=(shows every single event for every single subtype. contains similar information to _splice, but there is no splicing data for patients; there are also more entries because some uids are found in multiple subtypes. Contains columns for rawp, signature, and adjp which do not exist for _splice), 
    _fulldegene=(contains information for differentially expressed genes)
    """


    # Get column information for the selected table
    table_name = f"{cancer_prefix}{table_suffix}"
    columns = cancer_table_type_dict.get(table_suffix, [])

    # Build JSON output
    column_list = []
    for col in columns:
        col_name = col[0].replace("COLUMN NAME: ", "") if col[0].startswith("COLUMN NAME: ") else col[0]
        col_desc = col[1].replace("COLUMN DESCRIPTION: ", "") if col[1].startswith("COLUMN DESCRIPTION: ") else col[1]
        column_list.append({"column_name": col_name, "description": col_desc})

    result = {"table_name": table_name, "columns": column_list}
    return json.dumps(result, indent=2)