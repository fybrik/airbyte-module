curl --location --request POST 'http://127.0.0.1:8080/write_test' \
--header 'Content-Type: application/json' \
--data-raw '{"type": "RECORD","record": {"stream": "testing","data": {"DOB": "01/02/1988","FirstName": "John","LastNAME":"Jones"},"emitted_at": 1650284493000}}
'