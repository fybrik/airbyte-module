curl --location --request POST 'http://127.0.0.1:8080/userdata' \
--header @sample/header_file \
--data-raw '{"type": "RECORD","record": {"stream": "testing","data": {"DOB": "01/02/1988","FirstName": "John","LastNAME":"Jones"},"emitted_at": 1650284493000}}
'
