uv run scripts/register_segments_mert.py --dir "F:\song-recommender-data\data\shiny_colors" --segment-seconds 5 --device cuda --model "m-a-p/MERT-v1-95M" --collection "songs_segments_mert"
uv run scripts/register_segments_mert.py --dir "F:\song-recommender-data\data\kmnz" --segment-seconds 5 --device cuda --model "m-a-p/MERT-v1-95M" --collection "songs_segments_mert"
uv run scripts/register_segments_mert.py --dir "F:\song-recommender-data\data\Hikaru Utada" --segment-seconds 5 --device cuda --model "m-a-p/MERT-v1-95M" --collection "songs_segments_mert"
uv run scripts/register_segments_mert.py --dir "F:\song-recommender-data\data\ALSTROEMERIA" --segment-seconds 5 --device cuda --model "m-a-p/MERT-v1-95M" --collection "songs_segments_mert"

uv run scripts/register_segments_mert.py --dir "F:\song-recommender-data\data\shiny_colors" --segment-seconds 5 --device cuda --model "MIT/ast-finetuned-audioset-10-10-0.4593" --collection "songs_segments_ast"
uv run scripts/register_segments_mert.py --dir "F:\song-recommender-data\data\kmnz" --segment-seconds 5 --device cuda --model "MIT/ast-finetuned-audioset-10-10-0.4593" --collection "songs_segments_ast"
uv run scripts/register_segments_mert.py --dir "F:\song-recommender-data\data\kmnz" --segment-seconds 5 --device cuda --model "MIT/ast-finetuned-audioset-10-10-0.4593" --collection "songs_segments_ast"


uv run scripts/register_segments_mert.py --dir "F:\song-recommender-data\data\shiny_colors" --segment-seconds 5 --device cuda --model "MIT/ast-finetuned-audioset-10-10-0.4593" --collection "songs_segments_ast"
uv run scripts/register_segments_mert.py --dir "F:\song-recommender-data\data\kmnz" --segment-seconds 5 --device cuda --model "MIT/ast-finetuned-audioset-10-10-0.4593" --collection "songs_segments_ast"
uv run scripts/register_segments_mert.py --dir "F:\song-recommender-data\data\Hikaru Utada" --segment-seconds 5 --device cuda --model "MIT/ast-finetuned-audioset-10-10-0.4593" --collection "songs_segments_ast"
uv run scripts/register_segments_mert.py --dir "F:\song-recommender-data\data\ALSTROEMERIA" --segment-seconds 5 --device cuda --model "MIT/ast-finetuned-audioset-10-10-0.4593" --collection "songs_segments_ast"

uv run .\scripts\test_segment_features.py --search-filename "Sleepless Nights [2Dmjx6f47oU].wav" --exclude-same-song --search-collection songs_segments_mert --distance-max 0.1 --search-topk 5
uv run .\scripts\test_segment_features.py --search-filename "With you [s5-6ICR5kAE].wav" --exclude-same-song --search-collection songs_segments_mert --distance-max 0.1 --search-topk 5
uv run .\scripts\test_segment_features.py --search-filename "幻惑SILHOUETTE (2023 Ver.) [4LznTKY7XdA].wav" --exclude-same-song --search-collection songs_segments_mert --distance-max 0.1 --search-topk 5

uv run .\scripts\test_segment_features.py --search-filename "Sleepless Nights [2Dmjx6f47oU].wav" --exclude-same-song --search-collection songs_segments_balance --distance-max 0.1 --search-topk 5
uv run .\scripts\test_segment_features.py --search-filename "With you [s5-6ICR5kAE].wav" --exclude-same-song --search-collection songs_segments_balance --distance-max 0.1 --search-topk 5
uv run .\scripts\test_segment_features.py --search-filename "幻惑SILHOUETTE (2023 Ver.) [4LznTKY7XdA].wav" --exclude-same-song --search-collection songs_segments_balance --distance-max 0.1 --search-topk 5


uv run .\scripts\test_segment_features.py --search-filename "パステルカラー パスカラカラー [VyzV-6UWq8U].wav" --exclude-same-song --search-collection songs_segments_ast --distance-max 0.1
uv run .\scripts\test_segment_features.py --search-filename "パステルカラー パスカラカラー [VyzV-6UWq8U].wav" --exclude-same-song --search-collection songs_segments_mert --distance-max 0.1
uv run .\scripts\test_segment_features.py --search-filename "平行線の美学 [y6RIPflxByI].wav" --exclude-same-song --search-collection songs_segments_balanced --distance-max 0.1

uv run .\scripts\test_segment_features.py --search-filename "Love Addiction [f3fHCDNwTng].wav" --exclude-same-song --search-collection songs_segments_ast --distance-max 0.1

uv run .\scripts\test_segment_features.py --search-filename "とある英雄たちの物語 [X3G6sqNjqgc].wav" --exclude-same-song --search-collection songs_segments_ast --distance-max 0.1 --search-topk 5
