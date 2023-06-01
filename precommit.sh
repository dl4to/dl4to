echo "Cleaning notebooks"
nbdev_clean_nbs

echo "Building library"
rm dl4to/* -r
nbdev_build_lib

echo "Test notebooks"
nbdev_test_nbs

echo "Building documentation"
nbdev_build_docs
